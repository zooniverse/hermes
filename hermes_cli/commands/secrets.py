import sys

import boto3
import click
import dateutil

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


s3 = boto3.resource('s3')


def secret_s3_path(swarm_name, secret_name=''):
    return 'swarms/{}/secrets/{}'.format(swarm_name, secret_name)


def s3_config_bucket(ctx):
    config_bucket = ctx.parent.parent.config.get('s3_config_bucket')
    if not config_bucket:
        click.echo(
            'No s3_config_bucket configured! Please run hermes configure',
            err=True,
        )
        sys.exit(1)
    return config_bucket


def get_secrets(ctx, swarm_name, manager=None, skip_backups=False):
    config_bucket = s3_config_bucket(ctx)
    secrets = {
        'backups': {},
        'originals': {},
    }

    if not skip_backups:
        for s3_obj in s3.Bucket(config_bucket).objects.filter(
            Prefix=secret_s3_path(swarm_name),
        ):
            secret_name = s3_obj.key.split('/')[-1]
            secrets['backups'][secret_name] = {
                'id': '-',
                'name': secret_name,
                'backup': '-',
                'modified': s3_obj.last_modified,
            }

    def _get_originals(manager):
        for secret in manager.docker.secrets.list():
            secrets['originals'][secret.name] = {
                'id': secret.id,
                'name': secret.name,
                'backup': '*' if secret.name in secrets['backups'] else '!',
                'modified': dateutil.parser.parse(secret.attrs['UpdatedAt']),
            }

    if manager:
        _get_originals(manager)
    else:
        with Manager.find(swarm_name) as manager:
            _get_originals(manager)

    return secrets


def create_secret(swarm_name, secret_name, secret_data):
    with Manager.find(swarm_name) as manager:
        manager.docker.secrets.create(
            name=secret_name,
            data=secret_data,
        )


def get_backup(ctx, swarm_name, secret_name):
    return s3.Object(
        s3_config_bucket(ctx),
        secret_s3_path(swarm_name, secret_name),
    ).get()['Body'].read()


@cli.group()
def secrets():
    pass


@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('secret-name')
@click.argument('secret-file', type=click.File('rb'))
@click.option('-n', '--no-backup', is_flag=True)
def create(ctx, swarm_name, secret_name, secret_file, no_backup):
    if not no_backup:
        config_bucket = s3_config_bucket(ctx)

    secret_data = secret_file.read()

    create_secret(swarm_name, secret_name, secret_data)

    if not no_backup:
        s3.Object(
            config_bucket,
            secret_s3_path(swarm_name, secret_name),
        ).put(
            ServerSideEncryption='aws:kms',
            ACL='private',
            Body=secret_data,
        )


@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('secret-names', nargs=-1)
@click.option('--all', 'restore_all', is_flag=True)
def restore(ctx, swarm_name, secret_names, restore_all):
    secrets = get_secrets(ctx, swarm_name)

    if restore_all:
        secret_names = secrets['backups'].keys()

    count = 0
    for secret_name in secret_names:
        if secret_name in secrets['originals']:
            click.echo(
                "Warning: Original secret {} exists. Skipping restore.".format(
                    secret_name,
                ),
                err=True,
            )
            continue

        secret_data = get_backup(ctx, swarm_name, secret_name)
        create_secret(swarm_name, secret_name, secret_data)
        click.echo(secret_name)
        count += 1

    click.echo("Successfully restored {} secrets".format(count))


@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.option('-b', '--all-backups', is_flag=True)
def ls(ctx, swarm_name, all_backups):
    secrets = get_secrets(ctx, swarm_name)

    if all_backups:
        output_secrets = dict(secrets['backups'])
        output_secrets.update(secrets['originals'])
    else:
        output_secrets = secrets['originals']

    for secret in output_secrets.values():
        click.echo(
            "{backup} {id:<25}  {modified:%b %d %H:%M %Y %Z}  {name}".format(
                **secret
            ),
        )


@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('secret-names', nargs=-1)
@click.option('-f', '--force', is_flag=True)
def rm(ctx, swarm_name, secret_names, force):
    with Manager.find(swarm_name) as manager:
        secrets = get_secrets(
            ctx,
            swarm_name,
            manager,
            True,
        )

        for secret_name in secret_names:
            if secret_name not in secrets['originals']:
                click.echo(
                    "Error: Secret {} not found in swarm.".format(secret_name),
                    err=True,
                )
                sys.exit(1)

            secret = manager.docker.secrets.get(
                secrets['originals'][secret_name]['id']
            )

            if (
                force
                or click.confirm(
                    'Delete secret "{}"'.format(secret.name),
                    abort=True
                )
            ):
                secret.remove()


@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('secret-name')
def cat(ctx, swarm_name, secret_name):
    click.echo(
        get_backup(ctx, swarm_name, secret_name),
        nl=False,
    )

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

    with Manager.find(swarm_name) as manager:
        if not no_backup:
            s3.Object(
                config_bucket,
                secret_s3_path(swarm_name, secret_name),
            ).put(
                ServerSideEncryption='aws:kms',
                ACL='private',
                Body=secret_data,
            )
        manager.docker.secrets.create(
            name=secret_name,
            data=secret_data,
        )

@secrets.command()
@click.pass_context
@click.argument('swarm-name')
@click.option('-b', '--all-backups', is_flag=True)
def ls(ctx, swarm_name, all_backups):
    config_bucket = s3_config_bucket(ctx)
    backed_up_secrets = {}
    output_secrets = {}

    for s3_obj in s3.Bucket(config_bucket).objects.filter(
        Prefix=secret_s3_path(swarm_name),
    ):
        secret_name = s3_obj.key.split('/')[-1]
        backed_up_secrets[secret_name] = {
            'id': '-',
            'name': secret_name,
            'backup': '-',
            'modified': s3_obj.last_modified,
        }

    with Manager.find(swarm_name) as manager:
        for secret in manager.docker.secrets.list():
            output_secrets[secret.name] = {
                'id': secret.id,
                'name': secret.name,
                'backup': '*' if secret.name in backed_up_secrets else '!',
                'modified': dateutil.parser.parse(secret.attrs['UpdatedAt']),
            }

    if all_backups:
        backed_up_secrets.update(output_secrets)
        output_secrets = backed_up_secrets

    for secret in output_secrets.values():
        click.echo(
            "{backup} {id:<25}  {modified:%b %d %H:%M %Y %Z}  {name}".format(
                **secret
            ),
        )


@secrets.command()
@click.argument('swarm-name')
@click.argument('secret-id')
@click.option('-f', '--force', is_flag=True)
def rm(swarm_name, secret_id, force):
    with Manager.find(swarm_name) as manager:
        secret = manager.docker.secrets.get(secret_id)
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
@click.argument('secret-id')
def cat(ctx, swarm_name, secret_id):
    with Manager.find(swarm_name) as manager:
        secret = manager.docker.secrets.get(secret_id)
        config_bucket = s3_config_bucket(ctx)
        secret_data = s3.Object(
            config_bucket,
            secret_s3_path(swarm_name, secret.name),
        ).get()
        click.echo(
            secret_data['Body'].read(),
            nl=False,
        )

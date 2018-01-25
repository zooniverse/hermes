import sys

import boto3
import click
import dateutil

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


s3 = boto3.resource('s3')


def config_s3_path(swarm_name, config_name=''):
    return 'swarms/{}/configs/{}'.format(swarm_name, config_name)


def s3_config_bucket(ctx):
    config_bucket = ctx.parent.parent.config.get('s3_config_bucket')
    if not config_bucket:
        click.echo(
            'No s3_config_bucket configured! Please run hermes configure',
            err=True,
        )
        sys.exit(1)
    return config_bucket


def get_configs(ctx, swarm_name, manager=None, skip_backups=False):
    config_bucket = s3_config_bucket(ctx)
    configs = {
        'backups': {},
        'originals': {},
    }

    if not skip_backups:
        for s3_obj in s3.Bucket(config_bucket).objects.filter(
            Prefix=config_s3_path(swarm_name),
        ):
            config_name = s3_obj.key.split('/')[-1]
            configs['backups'][config_name] = {
                'id': '-',
                'name': config_name,
                'backup': '-',
                'modified': s3_obj.last_modified,
            }

    def _get_originals(manager):
        for config in manager.docker.configs.list():
            configs['originals'][config.name] = {
                'id': config.id,
                'name': config.name,
                'backup': '*' if config.name in configs['backups'] else '!',
                'modified': dateutil.parser.parse(config.attrs['UpdatedAt']),
            }

    if manager:
        _get_originals(manager)
    else:
        with Manager.find(swarm_name) as manager:
            _get_originals(manager)

    return configs


def create_config(swarm_name, config_name, config_data):
    with Manager.find(swarm_name) as manager:
        manager.docker.configs.create(
            name=config_name,
            data=config_data,
        )


def get_backup(ctx, swarm_name, config_name):
    return s3.Object(
        s3_config_bucket(ctx),
        config_s3_path(swarm_name, config_name),
    ).get()['Body'].read()


@cli.group()
def config():
    pass


@config.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('config-name')
@click.argument('config-file', type=click.File('rb'))
@click.option('-n', '--no-backup', is_flag=True)
def create(ctx, swarm_name, config_name, config_file, no_backup):
    if not no_backup:
        config_bucket = s3_config_bucket(ctx)

    config_data = config_file.read()

    create_config(swarm_name, config_name, config_data)

    if not no_backup:
        s3.Object(
            config_bucket,
            config_s3_path(swarm_name, config_name),
        ).put(
            ServerSideEncryption='aws:kms',
            ACL='private',
            Body=config_data,
        )


@config.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('config-names', nargs=-1)
@click.option('--all', 'restore_all', is_flag=True)
def restore(ctx, swarm_name, config_names, restore_all):
    configs = get_configs(ctx, swarm_name)

    if restore_all:
        config_names = configs['backups'].keys()

    count = 0
    for config_name in config_names:
        if config_name in configs['originals']:
            click.echo(
                "Warning: Original config {} exists. Skipping restore.".format(
                    config_name,
                ),
                err=True,
            )
            continue

        config_data = get_backup(ctx, swarm_name, config_name)
        create_config(swarm_name, config_name, config_data)
        click.echo(config_name)
        count += 1

    click.echo("Successfully restored {} configs".format(count))


@config.command()
@click.pass_context
@click.argument('swarm-name')
@click.option('-b', '--all-backups', is_flag=True)
def ls(ctx, swarm_name, all_backups):
    configs = get_configs(ctx, swarm_name)

    if all_backups:
        output_configs = dict(configs['backups'])
        output_configs.update(configs['originals'])
    else:
        output_configs = configs['originals']

    for config in output_configs.values():
        click.echo(
            "{backup} {id:<25}  {modified:%b %d %H:%M %Y %Z}  {name}".format(
                **config
            ),
        )


@config.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('config-names', nargs=-1)
@click.option('-f', '--force', is_flag=True)
def rm(ctx, swarm_name, config_names, force):
    with Manager.find(swarm_name) as manager:
        configs = get_configs(
            ctx,
            swarm_name,
            manager,
            True,
        )

        for config_name in config_names:
            if config_name not in configs['originals']:
                click.echo(
                    "Error: config {} not found in swarm.".format(config_name),
                    err=True,
                )
                sys.exit(1)

            config = manager.docker.configs.get(
                configs['originals'][config_name]['id']
            )

            if (
                force
                or click.confirm(
                    'Delete config "{}"'.format(config.name),
                    abort=True
                )
            ):
                config.remove()


@config.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('config-name')
def cat(ctx, swarm_name, config_name):
    click.echo(
        get_backup(ctx, swarm_name, config_name),
        nl=False,
    )

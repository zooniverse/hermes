import sys

import boto3
import click

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


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
        config_bucket = ctx.parent.parent.config.get('s3_config_bucket')
        if not config_bucket:
            click.echo(
                'No s3_config_bucket configured! Please run hermes configure',
                err=True,
            )
            sys.exit(1)

    secret_data = secret_file.read()

    with Manager.find(swarm_name) as manager:
        if not no_backup:
            boto3.resource('s3').Object(
                config_bucket,
                'swarms/{}/secrets/{}'.format(swarm_name, secret_name),
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
@click.argument('swarm-name')
def ls(swarm_name):
    with Manager.find(swarm_name) as manager:
        for secret in manager.docker.secrets.list():
            click.echo("{}\t{}".format(secret.id, secret.name))


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

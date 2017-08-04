import click

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


@cli.group()
def secrets():
    pass


@secrets.command()
@click.argument('swarm-name')
@click.argument('secret-name')
@click.argument('secret-file', type=click.File('rb'))
def create(swarm_name, secret_name, secret_file):
    with Manager.find(swarm_name) as manager:
        manager.docker.secrets.create(
            name=secret_name,
            data=secret_file.read(),
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

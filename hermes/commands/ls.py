import click

from hermes.manager import Manager
from hermes.scripts.hermes import cli


@cli.command()
@click.argument('stack-name', required=False)
def ls(stack_name=None):
    for manager in Manager.list(stack_name):
        click.echo(manager)

        manager.install_socat()
        manager.open_docker_socket()

        break

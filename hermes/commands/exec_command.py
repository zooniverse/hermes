import click
import subprocess
import sys

from hermes.manager import Manager
from hermes.scripts.hermes import cli


@cli.command()
@click.argument('swarm-name', required=True)
@click.argument('command', nargs=-1)
def exec(swarm_name, command):
    with Manager.find(swarm_name):
        exec_result = subprocess.call(
            command,
            stdin=click.get_text_stream('stdin'),
            stdout=click.get_text_stream('stdout'),
        )

    sys.exit(exec_result)

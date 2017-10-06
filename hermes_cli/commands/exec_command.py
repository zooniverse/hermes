import click
import subprocess
import sys

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


@cli.command(name="exec")
@click.argument('swarm-name', required=True)
@click.argument('command', nargs=-1)
@click.option(
    '--forward-port',
    '-F',
    required=False,
    type=str,
    help=(
        'Forward a port to localhost. '
        'Format: localport:networkname:remotehost:remoteport'
    ),
)
def exec_command(swarm_name, command, forward_port):
    if forward_port:
        try:
            (
                localport,
                networkname,
                remotehost,
                remoteport
            ) = forward_port.split(":")
        except ValueError:
            click.echo(
                (
                    'Error: Port forwarding requires '
                    'localport:networkname:remotehost:remoteport'
                ),
                err=True,
            )
            sys.exit(1)

        try:
            localport = int(localport)
        except ValueError:
            click.echo('Error: localport must be an integer', err=True)
            sys.exit(1)

        try:
            remoteport = int(remoteport)
        except ValueError:
            click.echo('Error: remoteport must be an integer', err=True)
            sys.exit(1)

    with Manager.find(swarm_name) as manager:
        if forward_port:
            manager.forward_port(
                localport,
                networkname,
                remotehost,
                remoteport,
            )

        exec_result = subprocess.call(
            command,
            stdin=click.get_text_stream('stdin'),
            stdout=click.get_text_stream('stdout'),
        )

    sys.exit(exec_result)

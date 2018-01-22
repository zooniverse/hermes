import os

import click
import yaml

from hermes_cli.manager import Manager


@click.group()
@click.pass_context
def cli(ctx):
    ctx.config_dir = os.path.expanduser('~/.hermes/')
    ctx.config_file = os.path.join(ctx.config_dir, 'config.yml')
    ctx.config = {
        'ssh_key_filename': 'autodetect',
        's3_config_bucket': '',
    }

    try:
        with open(ctx.config_file) as conf_f:
            ctx.config.update(yaml.load(conf_f))
    except IOError:
        pass

    Manager.configure(ctx.config)


from hermes_cli.commands.configure import *
from hermes_cli.commands.exec_command import *
from hermes_cli.commands.secret import *

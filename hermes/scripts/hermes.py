import os

import click
import yaml


@click.group()
@click.option('--region', '-r', type=str)
@click.pass_context
def cli(ctx, region):
    ctx.config_dir = os.path.expanduser('~/.hermes/')
    ctx.config_file = os.path.join(ctx.config_dir, 'config.yml')
    ctx.config = {
        'region': 'us-east-1',
        'access_key_id': '',
        'secret_access_key': '',
    }

    try:
        with open(ctx.config_file) as conf_f:
            ctx.config.update(yaml.load(conf_f))
    except IOError:
        pass

    if region:
        ctx.config['region'] = region


from hermes.commands.configure import *

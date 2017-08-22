import os

import click
import yaml

from hermes_cli.scripts.hermes import cli


@cli.command()
@click.pass_context
def configure(ctx):
    if not os.path.isdir(ctx.parent.config_dir):
        os.mkdir(ctx.parent.config_dir)

    for opt, value in ctx.parent.config.items():
        ctx.parent.config[opt] = click.prompt(
            opt,
            default=value
        )

    with open(ctx.parent.config_file, 'w') as conf_f:
        yaml.dump(ctx.parent.config, conf_f, default_flow_style=False)

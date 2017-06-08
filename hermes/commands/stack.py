import click
import yaml

from hermes.manager import Manager
from hermes.scripts.hermes import cli


@cli.group()
def stack():
    pass

@stack.command()
@click.argument('swarm-name', required=False)
def ls(swarm_name=None):
    manager = Manager.find(swarm_name)
    if not manager:
        return
    for stack in manager.docker.stacks.list():
        click.echo(stack.namespace)


@stack.command()
@click.argument('swarm-name')
@click.argument('stack-name')
def ps(swarm_name, stack_name):
    manager = Manager.find(swarm_name)
    if not manager:
        return
    stack = manager.docker.stacks.get(stack_name)
    for service in stack.services:
        click.echo(service.name)


@stack.command()
@click.argument('swarm-name')
@click.argument('stack-name')
def rm(swarm_name, stack_name):
    manager = Manager.find(swarm_name)
    if not manager:
        return
    stack = manager.docker.stacks.remove(stack_name)

@stack.command()
@click.argument('swarm-name')
@click.argument('stack-name')
@click.argument('compose-file', required=True, type=click.File('r'))
def deploy(swarm_name, stack_name, compose_file):
    compose_config = yaml.load(compose_file)
    manager = Manager.find(swarm_name)
    if not manager:
        return
    manager.docker.stacks.deploy(stack_name, compose_config)
    stack = manager.docker.stacks.get(stack_name)
    for service in stack.services:
        click.echo(service.name)

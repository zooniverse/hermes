import boto3
import click

from hermes_cli.scripts.hermes import cli


@cli.command()
@click.pass_context
@click.argument('swarm-name')
def deploy(ctx, swarm_name):
    ec2 = boto3.client('ec2')
    results = ec2.describe_instances(
        Filters=[
            {
                'Name': 'tag:aws:cloudformation:stack-name',
                'Values': [
                    swarm_name,
                ]
            },
            {
                'Name': 'tag:swarm-node-type',
                'Values': [
                    'manager',
                ]
            },
        ]
    )
    for reservation in results.get('Reservations', []):
        for instance in reservation.get('Instances', []):
            click.echo(instance['PublicDnsName'])

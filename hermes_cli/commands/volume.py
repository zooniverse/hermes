import io
import tarfile

import click

from hermes_cli.manager import Manager
from hermes_cli.scripts.hermes import cli


@cli.group()
def volume():
    pass


@volume.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('volume-name')
@click.argument('output-file', type=click.File('wb'))
@click.option('--driver', '-d', type=str, default='cloudstor:aws')
def backup(ctx, swarm_name, volume_name, output_file, driver):
    with Manager.find(swarm_name) as manager:
        backup_container = manager.docker.containers.create(
            image='alpine',
            volume_driver=driver,
            volumes={
                volume_name: {
                    'bind': '/mnt/{}'.format(volume_name),
                    'mode': 'ro',
                },
            },
        )
        backup_data, source_stat = backup_container.get_archive(
            '/mnt/{}/'.format(volume_name),
        )
        for chunk in backup_data.read_chunked():
            output_file.write(chunk)
        backup_container.remove(force=True)


@volume.command()
@click.pass_context
@click.argument('swarm-name')
@click.argument('volume-name')
@click.argument('input-file', type=click.File('rb'))
@click.option('--driver', '-d', type=str, default='cloudstor:aws')
@click.option('--strip', '-s', type=int, default=1)
def restore(ctx, swarm_name, volume_name, input_file, driver, strip):
    input_tar = tarfile.open(fileobj=input_file)
    output_file = io.BytesIO()
    output_tar = tarfile.open(fileobj=output_file, mode='w')

    for member in input_tar.getmembers():
        member_name = "/".join(member.name.split('/')[strip:])
        if member_name:
            member_f = input_tar.extractfile(member)
            member.name = member_name
            output_tar.addfile(member, member_f)

    output_tar.close()
    output_file.seek(0)

    with Manager.find(swarm_name) as manager:
        backup_container = manager.docker.containers.create(
            image='alpine',
            volume_driver=driver,
            volumes={
                volume_name: {
                    'bind': '/mnt/{}'.format(volume_name),
                    'mode': 'rw',
                },
            },
        )
        backup_container.put_archive(
            '/mnt/{}/'.format(volume_name),
            output_file.read()
        )
        backup_container.remove(force=True)

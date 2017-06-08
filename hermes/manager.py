import socket
import threading

import boto3
import click

from paramiko.client import SSHClient, MissingHostKeyPolicy

from hermes.docker import HermesDockerClient as DockerClient


class IgnorePolicy(MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return


class Manager(object):
    @classmethod
    def list(cls, stack=None):
        ec2 = boto3.client('ec2')
        filters = [
            {
                'Name': 'tag:swarm-node-type',
                'Values': [
                    'manager',
                ]
            },
        ]
        if stack:
            filters.append({
                'Name': 'tag:aws:cloudformation:stack-name',
                'Values': [
                    stack,
                ]
            })
        results = ec2.describe_instances(
            Filters=filters
        )
        for reservation in results.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                yield cls(instance)

    def __init__(self, instance):
        self.meta = instance
        self.stack = None
        for tag in instance['Tags']:
            if tag['Key'] == 'aws:cloudformation:stack-name':
                self.stack = tag['Value']
                break
        self.dns_name = instance['PublicDnsName']
        self.client = None
        self.docker_client = None
        self._socat_installed = False
        self._docker_listening = False

    def __str__(self):
        return "{} {} {}".format(
            self.stack,
            self.meta['State']['Name'],
            self.dns_name,
        )

    def connect_ssh(self, username='docker', key_filename=None):
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(IgnorePolicy())
        self.client.connect(
            self.dns_name,
            username=username,
            key_filename=key_filename,
        )

    def disconnect_ssh(self):
        self.client.close()

    def exec(self, command, echo_stdout=True, echo_stderr=True):
        if not self.client:
            self.connect_ssh()

        click.echo("{}@{} $ \033[1m{}\033[0m".format(
            self.meta['InstanceId'],
            self.stack,
            command,
        ))
        stdin, stdout, stderr = self.client.exec_command(command)

        if echo_stdout:
            for line in stdout.readlines():
                click.echo("\t\033[92m+ {}\033[0m".format(str(line).strip()))
        if echo_stderr:
            for line in stderr.readlines():
                click.echo(
                    "\t\033[91m- {}\033[0m".format(str(line).strip()),
                    err=True,
                )

        return stdin, stdout, stderr

    def install_socat(self):
        self.exec("sudo apk update")
        self.exec("sudo apk add socat")
        self._socat_installed = True

    def open_docker_socket(self):
        if not self._socat_installed:
            self.install_socat()

        self.docker_ssh_channel = self.client.get_transport().open_session()
        self.docker_ssh_channel.exec_command(
            "socat UNIX-CONNECT:/var/run/docker.sock STDIO"
        )

        local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_sock.bind(('127.0.0.1', 23750))
        local_sock.listen()

        def _accept_and_forward():
            self.local_connection, _ = local_sock.accept()

            def _recv_from_manager():
                while True:
                    self.local_connection.send(self.docker_ssh_channel.recv(1))

            def _send_to_manager():
                while True:
                    self.docker_ssh_channel.send(self.local_connection.recv(1))

            self.docker_recv_thread = threading.Thread(
                target=_recv_from_manager,
                daemon=True,
            )
            self.docker_recv_thread.start()

            self.docker_send_thread = threading.Thread(
                target=_send_to_manager,
                daemon=True,
            )
            self.docker_send_thread.start()

        self.accept_thread = threading.Thread(
            target=_accept_and_forward
        )
        self.accept_thread.start()
        self._docker_listening = True

    def init_docker_client(self):
        if not self._docker_listening:
            self.open_docker_socket()
        self.docker_client = DockerClient(
            base_url='tcp://127.0.0.1:23750',
        )

import os
import socket
import tempfile
import threading
import sys

import boto3
import click
import docker

from paramiko.client import SSHClient, MissingHostKeyPolicy


class IgnorePolicy(MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return


class Manager(object):
    config = {}

    @classmethod
    def list(cls, cf_stack=None):
        ec2 = boto3.client('ec2')
        filters = [
            {
                'Name': 'tag:swarm-node-type',
                'Values': [
                    'manager',
                ]
            },
            {
                'Name': 'instance-state-name',
                'Values': [
                    'running',
                ]
            },
        ]
        if cf_stack:
            filters.append({
                'Name': 'tag:aws:cloudformation:stack-name',
                'Values': [
                    cf_stack,
                ]
            })
        results = ec2.describe_instances(
            Filters=filters
        )
        for reservation in results.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                yield cls(instance)

    @classmethod
    def find(cls, stack=None):
        for manager in cls.list(stack):
            return manager
        click.echo(
            "Error: Manager not found for stack \"{}\"".format(stack),
            err=True,
        )
        sys.exit(1)

    @classmethod
    def configure(cls, config):
        Manager.config.update(config)

    def __init__(
        self,
        instance,
    ):
        self.meta = instance
        self.stack = None
        for tag in instance['Tags']:
            if tag['Key'] == 'aws:cloudformation:stack-name':
                self.stack = tag['Value']
                break
        self.dns_name = instance['PublicDnsName']
        self.docker_client = None
        self.ssh_client = None
        self._socat_installed = False
        self._docker_listening = False

    def __str__(self):
        return "{} {} {}".format(
            self.stack,
            self.meta['State']['Name'],
            self.dns_name,
        )

    def __enter__(self):
        self.open_docker_socket()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_docker_socket()

    def connect_ssh(self, username='docker'):
        key_filename = Manager.config.get('ssh_key_filename', None)
        if key_filename is 'autodetect':
            key_filename = None

        self.ssh_client = SSHClient()
        self.ssh_client.set_missing_host_key_policy(IgnorePolicy())
        self.ssh_client.connect(
            self.dns_name,
            username=username,
            key_filename=key_filename,
        )

    def disconnect_ssh(self):
        self.ssh_client.close()

    def execute(self, command, echo=True, echo_stdout=None, echo_stderr=None):
        if echo_stdout is None:
            echo_stdout = echo
        if echo_stderr is None:
            echo_stderr = echo

        if not self.ssh_client:
            self.connect_ssh()

        if echo:
            click.echo("{}@{} $ \033[1m{}\033[0m".format(
                self.meta['InstanceId'],
                self.stack,
                command,
            ))
        channel = self.ssh_client.get_transport().open_session()
        stdout = channel.makefile()
        stderr = channel.makefile_stderr()
        channel.exec_command(command)
        status = channel.recv_exit_status()

        if echo_stdout:
            for line in stdout.readlines():
                click.echo("\t\033[92m+ {}\033[0m".format(str(line).strip()))
        if echo_stderr:
            for line in stderr.readlines():
                click.echo(
                    "\t\033[91m- {}\033[0m".format(str(line).strip()),
                    err=True,
                )

        return status

    def install_socat(self):
        if self.execute("socat -V", echo=False) > 0:
            self.execute("sudo apk update")
            self.execute("sudo apk add socat")
        self._socat_installed = True

    def open_docker_socket(self):
        def _recv_send(
            side_a,
            side_b,
            cleanup_event,
        ):
            side_a.settimeout(1)
            while not cleanup_event.is_set():
                try:
                    side_b.send(
                        side_a.recv(1)
                    )
                except socket.timeout:
                    continue
                except OSError:
                    cleanup_event.set()
                    break
            side_a.close()

        def _accept_and_forward(listen_sock):
            while True:
                cleanup = threading.Event()

                client_connection, _ = listen_sock.accept()

                self.server_transport = self.ssh_client.get_transport()
                self.server_channel = self.server_transport.open_session()
                self.server_channel.exec_command(
                    "socat UNIX-CONNECT:/var/run/docker.sock STDIO"
                )

                send_to_server_thread = threading.Thread(
                    target=_recv_send,
                    args=(client_connection, self.server_channel, cleanup),
                    daemon=True,
                )
                send_to_server_thread.start()

                send_to_client_thread = threading.Thread(
                    target=_recv_send,
                    args=(self.server_channel, client_connection, cleanup),
                    daemon=True,
                )
                send_to_client_thread.start()

        if not self._socat_installed:
            self.install_socat()

        self.socket_prefix = tempfile.mkdtemp()
        self.socket_path = os.path.join(self.socket_prefix, 'docker.sock')

        self.listen_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listen_sock.bind(self.socket_path)
        self.listen_sock.listen()

        accept_thread = threading.Thread(
            target=_accept_and_forward,
            args=(self.listen_sock,),
            daemon=True,
        )
        accept_thread.start()
        self._docker_listening = True
        os.environ['DOCKER_HOST'] = "unix://{}".format(self.socket_path)

    def close_docker_socket(self):
        if not self._docker_listening:
            return

        self._docker_listening = False
        self.listen_sock.close()
        os.unlink(self.socket_path)
        os.rmdir(self.socket_prefix)

        if hasattr(self, 'server_channel'):
            self.server_channel.close()

    def init_docker_client(self):
        if not self._docker_listening:
            self.open_docker_socket()
        self.docker_client = docker.from_env()

    @property
    def docker(self):
        if not self.docker_client:
            self.init_docker_client()
        return self.docker_client

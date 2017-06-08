from docker import DockerClient
from docker.errors import NotFound
from docker.models.resource import Model, Collection


class HermesDockerClient(DockerClient):
    @property
    def stacks(self):
        return StackCollection(client=self)


class Stack(Model):
    @property
    def namespace(self):
        return self.attrs.get('namespace')

    @property
    def services(self):
        return self.attrs.get('services')

    def deploy(self, opts):
        for service_name, service_opts in opts.get('services', {}).items():
            service_opts['name'] = service_name
            service_opts.setdefault('labels', {}).update({
                'com.docker.stack.namespace': self.namespace,
            })
            # TODO add support for these
            service_opts.pop('healthcheck', None)
            service_opts.pop('deploy', None)
            service_opts.pop('secrets', None)
            service_opts.pop('ports', None)
            self.client.services.create(**service_opts)

    def remove(self):
        for service in self.services:
            service.remove()


class StackCollection(Collection):
    model = Stack

    def deploy(self, namespace, opts):
        try:
            stack = self.get(namespace)
        except NotFound:
            stack = self.prepare_model({
                'namespace': namespace,
            })
        return stack.deploy(opts)

    def get(self, namespace):
        for stack in self.list():
            if stack.namespace == namespace:
                return stack
        raise NotFound('Could not find stack: {}'.format(namespace))

    def list(self, **kwargs):
        stacks = dict()
        for service in self.client.services.list():
            try:
                labels = service.attrs['Spec']['Labels']
                namespace = labels['com.docker.stack.namespace']
            except KeyError:
                continue
            stacks.setdefault(
                namespace,
                [],
            ).append(service)
        return [
            self.prepare_model({
                'namespace': namespace,
                'services': services,
            })
            for namespace, services in stacks.items()
        ]

    def remove(self, namespace):
        self.get(namespace).remove()

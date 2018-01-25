# hermes
A CLI for deploying stacks to Docker Swarm on AWS

To install:

```
pip3 install git+git://github.com/zooniverse/hermes.git
```


See what's running:

```
hermes exec StandaloneAppsSwarm -- docker stack ps comms-staging
```

Install/Update a stack:

```
hermes exec StandaloneAppsSwarm -- docker stack deploy -c comms-staging.yml comms-staging
```

To publicly expose an HTTP service:

* Add domain to this: https://github.com/zooniverse/static/blob/master/sites/standalone-swarm.conf
* Add the `public-web` network to the service in the stack definition. See Caesar or EducationAPI for an example.
* Log in to AWS, open the Route 53 configuration. Add a record set pointing to `static-elb`.

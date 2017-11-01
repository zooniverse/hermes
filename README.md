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

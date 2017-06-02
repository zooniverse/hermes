from setuptools import setup, find_packages

setup(
    name='hermescli',
    version='0.1',
    url='https://github.com/zooniverse/hermes',
    author='Adam McMaster',
    author_email='adam@zooniverse.org',
    description=(
        'A CLI for deploying stacks to Docker Swarm on AWS'
    ),
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'docker',
        'paramiko',
        'boto3',
        'PyYAML',
    ],
    entry_points='''
        [console_scripts]
        hermes=hermes.scripts.hermes:cli
    ''',
)

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
        'boto3<1.7',
        'PyYAML',
        'python-dateutil<2.7.0',
    ],
    entry_points='''
        [console_scripts]
        hermes=hermes_cli.scripts.hermes:cli
    ''',
)

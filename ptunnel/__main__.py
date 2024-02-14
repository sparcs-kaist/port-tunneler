import click
import logging
import pathlib

import ptunnel

__version__ = "1.0.0-pre1"
ptunnel.__version__ = __version__

@click.version_option(prog_name="ptunnel", version=__version__)
@click.group()
def main():
    """
    Simple port forwarding tool for SPARCS.
    """
    pass

@main.command("server")
@click.option("-c", "--config", default="config.json", help="Path to the config file.")
def crontab(user, config):
    """
    Server run.
    """
    config = ptunnel.config.load(config)
    crontab = ptunnel.crontab.generate(config, user)
    print(crontab)

@main.command("client")
@click.argument("config", default="/etc/mirror/daemon.json")
def daemon(config):
    """
    Client run.
    """
    config = ptunnel.config.load(config)
    ptunnel.client.daemon(config)

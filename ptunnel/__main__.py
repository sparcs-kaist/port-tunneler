import click
import logging
import pathlib

import ptunnel
import ptunnel.client
import ptunnel.server

__version__ = "1.0.0-pre4"
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
def crontab(config):
    """
    Server run.
    """
    config = ptunnel.server.load_config(config)
    ptunnel.server.run(config)

@main.command("config")
def config():
    """
    Config file management.
    """
    ptunnel.server.save_config()

@main.command("client")
def daemon(config):
    """
    Client run.
    """
    ptunnel.client.run(config)

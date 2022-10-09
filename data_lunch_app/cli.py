import click
import pkg_resources
from hydra import compose, initialize
from omegaconf import OmegaConf
import os
from .models import create_database, create_engine

# Import database object
from .models import db as sql_alchemy_db
from .models import Menu, Orders

# Version
__version__ = pkg_resources.require("data_lunch_cli")[0].version


# CLI COMMANDS ----------------------------------------------------------------
print(os.getcwd())


@click.group()
@click.version_option(__version__)
@click.pass_context
def cli(ctx):
    """Command line interface for creating a local sqlite database.
    To be used only for development purposes.
    """

    # global initialization
    initialize(config_path="conf", job_name="data_lunch_cli")
    config = compose(config_name="config")
    ctx.obj = {"config": config}


@cli.group()
@click.pass_obj
def db(obj):
    """Manage the database."""


@db.command("init")
@click.pass_obj
def init_database(obj):
    """Initialize the database."""

    # Create database
    create_database(obj["config"])

    click.secho("Database initialized", fg="green")


@db.command("delete")
@click.confirmation_option()
@click.pass_obj
def delete_database(obj):
    """Delete the database."""

    # Create database
    try:
        engine = create_engine(obj["config"])
        sql_alchemy_db.metadata.drop_all(engine)
        click.secho("Database deleted", fg="green")
    except Exception:
        # Generic error
        click.secho("Cannot delete database for unknown reason", fg="red")


def main():
    cli(auto_envvar_prefix="DATA_LUNCH")


if __name__ == "__main__":
    main()

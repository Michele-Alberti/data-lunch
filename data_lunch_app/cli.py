import click
import pkg_resources
from hydra import compose, initialize
from omegaconf import OmegaConf
import os
from .models import create_database, create_engine

# Import database object
from .models import db as sql_alchemy_db
from .models import Menu, Orders, Users, Stats

# Import functions from core
from .core import clean_tables as clean_tables_func

# Version
__version__ = pkg_resources.require("data_lunch_cli")[0].version


# CLI COMMANDS ----------------------------------------------------------------


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
        click.secho("Cannot delete database for unknown reasons", fg="red")


@db.command("clean")
@click.confirmation_option()
@click.pass_obj
def clean_tables(obj):
    """Clean 'users', 'menu' and 'orders' tables."""

    # Drop table
    try:
        clean_tables_func(obj["config"])
        click.secho("done", fg="green")
    except Exception:
        # Generic error
        click.secho("Cannot clean database for unknown reasons", fg="red")


@db.group()
@click.pass_obj
def table(obj):
    """Manage tables in database."""


@table.command("drop")
@click.confirmation_option()
@click.argument("name")
@click.pass_obj
def delete_table(obj, name):
    """Drop a single table from database."""

    # Drop table
    try:
        engine = create_engine(obj["config"])
        command = f"DROP TABLE {name};"
        engine.execute(command)
        click.secho(f"Table '{name}' deleted", fg="green")
    except Exception:
        # Generic error
        click.secho("Cannot delete database for unknown reasons", fg="red")


def main():
    cli(auto_envvar_prefix="DATA_LUNCH")


if __name__ == "__main__":
    main()

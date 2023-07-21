import click
import pkg_resources
from hydra import compose, initialize
from omegaconf import OmegaConf
import pandas as pd
import panel as pn
from .models import create_database, create_engine

# Import database object
from .models import db as sql_alchemy_db
from .models import Menu, Orders, Users, Stats

# Import functions from core
from .core import clean_tables as clean_tables_func

# Auth
from .auth import list_users, add_user_hashed_password, remove_user

# Version
__version__ = pkg_resources.require("data_lunch")[0].version


# CLI COMMANDS ----------------------------------------------------------------


@click.group()
@click.version_option(__version__)
@click.pass_context
def cli(ctx):
    """Command line interface for creating a local sqlite database.
    To be used only for development purposes.
    """

    # global initialization
    initialize(
        config_path="conf", job_name="data_lunch_cli", version_base="1.3"
    )
    config = compose(config_name="config")
    ctx.obj = {"config": config}


@cli.group()
@click.pass_obj
def cache(obj):
    """Manage cache."""


@cache.command("clean")
@click.confirmation_option()
@click.pass_obj
def clean_caches(obj):
    """Clean caches."""

    # Clear action
    pn.state.clear_caches()

    click.secho("Caches cleared", fg="green")


@cli.group()
@click.pass_obj
def credentials(obj):
    """Manage users credentials."""


@credentials.command("list")
@click.pass_obj
def list_users_name(obj):
    """List users."""

    # Clear action
    usernames = list_users()
    click.secho("USERS:")
    click.secho("\n".join(usernames), fg="yellow")
    click.secho("\nDone", fg="green")


@credentials.command("add")
@click.argument("user")
@click.argument("password")
@click.pass_obj
def add_user_psw(obj, user, password):
    """Add users credentials."""

    # Add hashed password to credentials file
    add_user_hashed_password(user, password)

    click.secho(f"User '{user}' added", fg="green")


@credentials.command("remove")
@click.confirmation_option()
@click.argument("user")
@click.pass_obj
def remove_user_psw(obj, user):
    """Remove user."""

    # Clear action
    remove_user(user)

    click.secho(f"User '{user}' removed", fg="green")


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
    except Exception as e:
        # Generic error
        click.secho("Cannot delete database", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


@db.command("clean")
@click.confirmation_option()
@click.pass_obj
def clean_tables(obj):
    """Clean 'users', 'menu', 'orders' and 'flags' tables."""

    # Drop table
    try:
        clean_tables_func(obj["config"])
        click.secho("done", fg="green")
    except Exception as e:
        # Generic error
        click.secho("Cannot clean database", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


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
    except Exception as e:
        # Generic error
        click.secho("Cannot drop table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


@table.command("export")
@click.argument("name")
@click.argument("csv_file_path")
@click.option("--index/--no-index", "index", show_default=True, default=False)
@click.pass_obj
def export_table_to_csv(obj, name, csv_file_path, index):
    """Export a single table to a csv file."""

    click.secho(f"Export table '{name}' to CSV {csv_file_path}", fg="yellow")

    # Create dataframe
    try:
        engine = create_engine(obj["config"])
        df = pd.read_sql_table(name, engine)
    except Exception as e:
        # Generic error
        click.secho("Cannot read table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")

    # Show head
    click.echo("First three rows of the table")
    click.echo(f"{df.head(3)}\n")

    # Export table
    try:
        df.to_csv(csv_file_path, index=index)
    except Exception as e:
        # Generic error
        click.secho("Cannot write CSV", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")

    click.secho("Done", fg="green")


@table.command("load")
@click.confirmation_option()
@click.argument("name")
@click.argument("csv_file_path")
@click.option("--index/--no-index", "index", show_default=True, default=True)
@click.option("-l", "--index-label", "index_label", type=str, default=None)
@click.option("-c", "--index-col", "index_col", type=str, default=None)
@click.option(
    "-e",
    "--if-exists",
    "if_exists",
    type=click.Choice(["fail", "replace", "append"], case_sensitive=False),
    show_default=True,
    default="append",
)
@click.pass_obj
def load_table(
    obj, name, csv_file_path, index, index_label, index_col, if_exists
):
    """Load a single table from a csv file."""

    click.secho(f"Load CSV {csv_file_path} to table '{name}'", fg="yellow")

    # Create dataframe
    df = pd.read_csv(csv_file_path, index_col=index_col)

    # Show head
    click.echo("First three rows of the CSV table")
    click.echo(f"{df.head(3)}\n")

    # Load table
    try:
        engine = create_engine(obj["config"])
        df.to_sql(
            name,
            engine,
            index=index,
            index_label=index_label,
            if_exists=if_exists,
        )
        click.secho("Done", fg="green")
    except Exception as e:
        # Generic error
        click.secho("Cannot load table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


def main():
    cli(auto_envvar_prefix="DATA_LUNCH")


if __name__ == "__main__":
    main()

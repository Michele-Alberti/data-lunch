"""Module with Data-Lunch's command line.

The command line is built with `click`.

Call `data-lunch --help` from the terminal inside an environment where the
`dlunch` package is installed.
"""

import click
import pkg_resources
import pandas as pd
import subprocess

from hydra import compose, initialize

# Database imports
from .models import Data, metadata_obj, CommonTable

# Waiter Imports
from .core import Waiter

# Auth imports
from . import auth

# Version
__version__: str = pkg_resources.require("dlunch")[0].version
"""Data-Lunch command line version."""


# CLI COMMANDS ----------------------------------------------------------------


@click.group()
@click.version_option(__version__)
@click.option(
    "-o",
    "--hydra-overrides",
    "hydra_overrides",
    default=None,
    multiple=True,
    help="pass hydra override, use multiple time to add more than one override",
)
@click.pass_context
def cli(ctx, hydra_overrides: tuple | None):
    """Command line interface for managing Data-Lunch database and users."""
    # global initialization
    initialize(
        config_path="conf", job_name="data_lunch_cli", version_base="1.3"
    )
    config = compose(config_name="config", overrides=hydra_overrides)

    # Instance auth context and waiter
    auth_context = auth.AuthContext(config=config)
    waiter = Waiter(config=config)

    # Store common objects in context
    ctx.obj = {
        "config": config,
        "auth_context": auth_context,
        "waiter": waiter,
    }

    # Auth encryption
    auth_context.set_app_auth_and_encryption()


@cli.group()
@click.pass_obj
def users(obj):
    """Manage privileged users and their group."""


@users.command("list")
@click.option(
    "--privileged-only",
    "list_only_privileged_users",
    is_flag=True,
    help="list only privileged users (without group)",
)
@click.pass_obj
def list_users(obj, list_only_privileged_users):
    """List users and privileges."""

    # Define padding function
    def _left_justify(df):
        df = df.astype(str).str.strip()
        return df.str.ljust(df.str.len().max())

    # Auth settings
    auth_type = obj["auth_context"].auth_type() or "not active"
    click.secho("AUTH SETTINGS", fg="yellow", bold=True)
    click.secho(f"authentication: {auth_type}\n")

    # List user
    click.secho("USERS", fg="yellow", bold=True)
    if list_only_privileged_users:
        users = obj["auth_context"].list_privileged_users()
        click.secho("user", fg="cyan")
        click.secho("\n".join(users))
    else:
        df_users = obj["auth_context"].list_users_guests_and_privileges()
        df_users = (
            df_users.reset_index()
            .apply(_left_justify)
            .to_string(index=False, justify="left")
        )
        click.secho(df_users.split("\n")[0], fg="cyan")
        click.secho("\n".join(df_users.split("\n")[1:]))

    click.secho("\nDone", fg="green")


@users.command("add")
@click.argument("user")
@click.option("--admin", "is_admin", is_flag=True, help="add admin privileges")
@click.pass_obj
def add_privileged_user(obj, user, is_admin):
    """Add privileged users (with or without admin privileges)."""

    # Add privileged user to 'privileged_users' table
    auth_user = auth.AuthUser(config=obj["config"], name=user)
    auth_user.add_privileged_user(is_admin=is_admin)

    click.secho(f"User '{user}' added (admin: {is_admin})", fg="green")


@users.command("remove")
@click.confirmation_option()
@click.argument("user")
@click.pass_obj
def remove_privileged_user(obj, user):
    """Remove user from both privileged users and basic login credentials table."""

    # Clear action
    deleted_data = auth.AuthUser(config=obj["config"], name=user).remove_user()

    if (deleted_data["privileged_users_deleted"] > 0) or (
        deleted_data["credentials_deleted"] > 0
    ):
        click.secho(
            f"User '{user}' removed (auth: {deleted_data['privileged_users_deleted']}, cred: {deleted_data['credentials_deleted']})",
            fg="green",
        )
    else:
        click.secho(f"User '{user}' does not exist", fg="yellow")


@cli.group()
@click.pass_obj
def credentials(obj):
    """Manage users credentials for basic authentication."""


@credentials.command("add")
@click.argument("user")
@click.argument("password")
@click.option("--admin", "is_admin", is_flag=True, help="add admin privileges")
@click.option(
    "--guest",
    "is_guest",
    is_flag=True,
    help="add user as guest (not added to privileged users)",
)
@click.pass_obj
def add_user_credential(obj, user, password, is_admin, is_guest):
    """Add users credentials to credentials table (used by basic authentication)
    and to privileged users (if not guest)."""

    # Add a privileged users only if guest option is not active
    auth_user = auth.AuthUser(config=obj["config"], name=user)
    if not is_guest:
        auth_user.add_privileged_user(is_admin=is_admin)
    # Add hashed password to credentials table
    auth_user.add_user_hashed_password(password)

    click.secho(f"User '{user}' added", fg="green")


@credentials.command("remove")
@click.confirmation_option()
@click.argument("user")
@click.pass_obj
def remove_user_credential(obj, user):
    """Remove user from both privileged users and basic login credentials table."""

    # Clear action
    deleted_data = auth.AuthUser(config=obj["config"], name=user).remove_user()

    if (deleted_data["privileged_users_deleted"] > 0) or (
        deleted_data["credentials_deleted"] > 0
    ):
        click.secho(
            f"User '{user}' removed (auth: {deleted_data['privileged_users_deleted']}, cred: {deleted_data['credentials_deleted']})",
            fg="green",
        )
    else:
        click.secho(f"User '{user}' does not exist", fg="yellow")


@cli.group()
@click.pass_obj
def db(obj):
    """Manage the database."""


@db.command("init")
@click.option(
    "--add-basic-auth-users",
    "add_basic_auth_users",
    is_flag=True,
    help="automatically create basic auth standard users",
)
@click.pass_obj
def init_database(obj, add_basic_auth_users):
    """Initialize the database."""

    # Create database
    waiter: Waiter = obj["waiter"]
    waiter.database_connector.create_database(
        add_basic_auth_users=add_basic_auth_users
    )

    click.secho(
        f"Database initialized (basic auth users: {add_basic_auth_users})",
        fg="green",
    )


@db.command("delete")
@click.confirmation_option()
@click.pass_obj
def delete_database(obj):
    """Delete the database."""

    # Create database
    waiter: Waiter = obj["waiter"]
    try:
        engine = waiter.database_connector.create_engine()
        Data.metadata.drop_all(engine)
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
        obj["waiter"].clean_tables()
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
    waiter: Waiter = obj["waiter"]
    try:
        engine = waiter.database_connector.create_engine()
        metadata_obj.tables[name].drop(engine)
        click.secho(f"Table '{name}' deleted", fg="green")
    except Exception as e:
        # Generic error
        click.secho("Cannot drop table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


@table.command("export")
@click.argument("name")
@click.argument("csv_file_path")
@click.option(
    "--index/--no-index",
    "index",
    show_default=True,
    default=False,
    help="select if index column is exported to csv",
)
@click.pass_obj
def export_table_to_csv(obj, name, csv_file_path, index):
    """Export a single table to a csv file."""

    click.secho(f"Export table '{name}' to CSV {csv_file_path}\n", fg="yellow")

    # Instantiate model
    model = None
    try:
        # Find model
        for mapper in Data.registry.mappers:
            if mapper.class_.__tablename__ == name:
                model: CommonTable = mapper.class_
                break

        # Raise error if can't find a valid table
        if model is None:
            raise Exception(f"Table '{name}' not found")

        # Create dataframe
        df = model.read_as_df(obj["config"])

    except Exception as e:
        # Generic error
        click.secho("Cannot read table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")
    else:
        # Show head
        click.echo("First three rows of the table (index included)\n")
        click.secho(
            df.head(3).to_string(index=False).split("\n")[0], fg="cyan"
        )
        click.secho(
            "\n".join(df.head(3).to_string(index=False).split("\n")[1:])
        )

        # Export table
        try:
            df.to_csv(csv_file_path, index=index)
        except Exception as e:
            # Generic error
            click.secho("Cannot write CSV", fg="red")
            click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")
        else:
            click.secho("Done", fg="green")


@table.command("load")
@click.confirmation_option()
@click.argument("name")
@click.argument("csv_file_path")
@click.option(
    "--index/--no-index",
    "index",
    show_default=True,
    default=True,
    help="select if index column is uploaded to table",
)
@click.option(
    "-c",
    "--index-col",
    "index_col",
    type=str,
    default=None,
    help="select the column used as index in the csv file",
)
@click.pass_obj
def load_table(obj, name, csv_file_path, index, index_col):
    """Load a single table from a csv file."""

    click.secho(f"Load CSV {csv_file_path} to table '{name}'", fg="yellow")

    # Create dataframe
    df = pd.read_csv(csv_file_path, index_col=index_col)

    # Show head
    click.echo("First three rows of the table to upload\n")
    header_rows = 2 if index_col else 1
    click.secho(
        "\n".join(df.head(3).to_string().split("\n")[:header_rows]), fg="cyan"
    )
    click.secho("\n".join(df.head(3).to_string().split("\n")[header_rows:]))

    # Instantiate model
    model = None

    try:
        # Find model
        for mapper in Data.registry.mappers:
            if mapper.class_.__tablename__ == name:
                model: CommonTable = mapper.class_
                break

        # Raise error if can't find a valid table
        if model is None:
            raise Exception(f"Table '{name}' not found")

        num_rows_written = model.write_from_df(
            config=obj["config"],
            df=df,
            index=index,
        )
        click.secho(f"\nUpload complete ({num_rows_written} rows)", fg="green")
    except Exception as e:
        # Generic error
        click.secho("Cannot load table", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


@cli.group()
@click.pass_obj
def utils(obj):
    """Utility commands."""


@utils.command("generate-secrets")
@click.pass_obj
def generate_secrets(obj):
    """Generate secrets for DATA_LUNCH_COOKIE_SECRET and DATA_LUNCH_OAUTH_ENC_KEY env variables."""

    try:
        result_secret = subprocess.run(
            ["panel", "secret"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        click.secho("\nCOOKIE SECRET:", fg="yellow", bold=True)
        click.secho(
            f"{result_secret.stdout.decode('utf-8')}",
            fg="cyan",
        )
        result_encription = subprocess.run(
            ["panel", "oauth-secret"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        click.secho("ENCRIPTION KEY:", fg="yellow", bold=True)
        click.secho(
            f"{result_encription.stdout.decode('utf-8')}",
            fg="cyan",
        )
        click.secho("Done", fg="green")
    except Exception as e:
        # Generic error
        click.secho("Cannot generate secrets", fg="red")
        click.secho(f"\n ===== EXCEPTION =====\n\n{e}", fg="red")


def main() -> None:
    """Main command line entrypoint."""
    cli(auto_envvar_prefix="DATA_LUNCH")


if __name__ == "__main__":
    main()

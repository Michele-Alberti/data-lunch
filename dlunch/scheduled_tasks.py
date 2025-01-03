"""Module with functions used to execute scheduled tasks.

See https://panel.holoviz.org/how_to/callbacks/schedule.html for details.
"""

import logging
import datetime as dt
from omegaconf import DictConfig

from . import auth
from . import cloud
from . import core
from . import models

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# FUNCTIONS -------------------------------------------------------------------
# The first argument of every scheduled task shall be Hydra's overall
# configuration


def clean_files_db(config: DictConfig) -> callable:
    """Return a callable object for cleaning temporary tables and files.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        callable: function to be scheduled.
    """

    # Create instance of Waiter
    waiter = core.Waiter(config=config)

    async def scheduled_function() -> None:
        """Clean menu, orders, users and flags tables. Delete also local files."""
        log.info(f"clean task (files and db) executed at {dt.datetime.now()}")
        # Delete files
        waiter.delete_files()
        # Clean tables
        waiter.clean_tables()

    return scheduled_function


def reset_guest_user_password(config: DictConfig) -> callable:
    """Return a callable object for resetting guest user password.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        callable: function to be scheduled.
    """

    # Create instance of AuthContext
    auth_context = auth.AuthContext(config=config)

    async def scheduled_function() -> None:
        """Reset guest user password."""
        log.info(f"reset guest user password executed at {dt.datetime.now()}")
        # Change reset flag
        models.set_flag(
            config=config, id="reset_guest_user_password", value=True
        )
        # Reset password
        auth_context.set_guest_user_password()

    return scheduled_function


def upload_db_to_gcp_storage(config: DictConfig, **kwargs) -> callable:
    """Return a callable object for uploading database to google cloud storage.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        callable: function to be scheduled.
    """

    async def scheduled_function() -> None:
        """Upload database to GCP storage."""
        log.info(
            f"upload database to gcp storage executed at {dt.datetime.now()}"
        )
        # Upload database
        cloud.upload_to_gcloud(**kwargs)

    return scheduled_function

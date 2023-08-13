import logging
import datetime as dt
from omegaconf import DictConfig

from . import core
from . import cloud
from . import models

# LOGGER ----------------------------------------------------------------------
log = logging.getLogger(__name__)


# FUNCTIONS -------------------------------------------------------------------
# The first argument of every scheduled task shall be Hydra's overall
# configuration


def clean_files_db(config: DictConfig):
    """return a callable object for cleaning temporary tables and files"""

    async def scheduled_function():
        log.info(f"clean task (files and db) executed at {dt.datetime.now()}")
        # Delete files
        core.delete_files(config)
        # Clean tables
        core.clean_tables(config)

    return scheduled_function


def reset_guest_user_password(config: DictConfig):
    """return a callable object for resetting guest user password"""

    async def scheduled_function():
        log.info(f"reset guest user password executed at {dt.datetime.now()}")
        # Change reset flag
        models.set_flag(
            config=config, id="reset_guest_user_password", value=True
        )
        # Reset password
        core.set_guest_user_password(config)

    return scheduled_function


def upload_db_to_gcp_storage(config: DictConfig, **kwargs):
    """return a callable object for uploading database to google cloud storage"""

    async def scheduled_function():
        log.info(
            f"upload database to gcp storage executed at {dt.datetime.now()}"
        )
        # Upload database
        cloud.upload_to_gcloud(**kwargs)

    return scheduled_function

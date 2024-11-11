"""Data-Lunch package entrypoint."""

import datetime as dt
import hydra
import logging
import panel as pn
from collections.abc import Callable
from omegaconf import DictConfig, OmegaConf
from omegaconf.errors import ConfigAttributeError
from . import auth
from . import create_app, create_backend
from . import models

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# PANEL EXTENSIONS ------------------------------------------------------------
# Set panel extensions
log.debug("set extensions")
pn.extension(
    "tabulator",
)


# FUNCTIONS -------------------------------------------------------------------
@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def run_app(config: DictConfig) -> None:
    """Main entrypoint, start the app loop.

    Initialize database, authentication and encription.
    Setup panel and create objects for frontend and backend.

    Args:
        config (DictConfig): hydra configuration object.
    """
    # Starting scheduled cleaning
    if config.panel.scheduled_tasks:
        for task in config.panel.scheduled_tasks:
            schedule_task(
                **task.kwargs,
                callable=hydra.utils.instantiate(task.callable, config),
            )

    # Set auth configurations
    log.info("set auth config and encryption")
    # Auth encryption
    auth.set_app_auth_and_encryption(config)
    log.debug(
        f'authentication {"" if auth.is_auth_active(config) else "not "}active'
    )

    log.info("set panel config")
    # Set notifications options
    pn.extension(
        disconnect_notification=config.panel.notifications.disconnect_notification,
        ready_notification=config.panel.notifications.ready_notification,
    )
    # Configurations
    pn.config.nthreads = config.panel.nthreads
    pn.config.notifications = True
    authorize_callback_factory = hydra.utils.call(
        config.auth.authorization_callback, config
    )
    pn.config.authorize_callback = lambda ui, tp: authorize_callback_factory(
        user_info=ui, target_path=tp
    )
    pn.config.auth_template = config.auth.auth_error_template

    # If basic auth is used the database and users credentials shall be created here
    if auth.is_basic_auth_active:
        log.info("initialize database and users credentials for basic auth")
        # Create tables
        models.create_database(
            config,
            add_basic_auth_users=auth.is_basic_auth_active(config=config),
        )

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app and create_backend function as a lambda function to
    # ensure that each invocation has a dedicated state variable (users'
    # selections are not shared between instances)
    # Backend exist only if auth is active
    # Health is an endpoint for app health assessments
    # Pass a dictionary for a multipage app
    pages = {"": lambda: create_app(config=config)}
    if auth.is_auth_active(config=config):
        pages["backend"] = lambda: create_backend(config=config)

    # If basic authentication is active, instantiate ta special auth object
    # otherwise leave an empty dict
    # This step is done before panel.serve because auth_provider requires that
    # the whole config is passed as an input
    if auth.is_basic_auth_active(config=config):
        auth_object = {
            "auth_provider": hydra.utils.instantiate(
                config.basic_auth.auth_provider, config
            )
        }
        log.debug(
            "auth_object dict set to instantiated object from config.server.auth_provider"
        )
    else:
        auth_object = {}
        log.debug(
            "missing config.server.auth_provider, auth_object dict left empty"
        )

    # Set session begin/end logs
    pn.state.on_session_created(lambda ctx: log.debug("session created"))
    pn.state.on_session_destroyed(lambda ctx: log.debug("session closed"))

    pn.serve(
        panels=pages, **hydra.utils.instantiate(config.server), **auth_object
    )


def schedule_task(
    name: str,
    enabled: bool,
    hour: int | None,
    minute: int | None,
    period: str,
    callable: Callable,
) -> None:
    """Schedule a task execution using Panel.

    Args:
        name (str): task name (used for logs).
        enabled (bool): flag that marks a task as enabled.
            tasks are not executed if disabled.
        hour (int | None): start hour (used only if also minute is not None).
        minute (int | None): start minute (used only if also hour is not None).
        period (str): the period between executions.
            May be expressed as a timedelta or a string.

            * Week: `'1w'`
            * Day: `'1d'`
            * Hour: `'1h'`
            * Minute: `'1m'`
            * Second: `'1s'`

        callable (Callable): the task to be executed.
    """
    # Starting scheduled tasks (if enabled)
    if enabled:
        log.info(f"starting task '{name}'")
        if (hour is not None) and (minute is not None):
            start_time = dt.datetime.today().replace(
                hour=hour,
                minute=minute,
            )
            # Set start time to tomorrow if the time already passed
            if start_time < dt.datetime.now():
                start_time = start_time + dt.timedelta(days=1)
            log.info(
                f"starting time: {start_time.strftime('%Y-%m-%d %H:%M')} - period: {period}"
            )
        else:
            start_time = None
            log.info(f"starting time: now - period: {period}")
        pn.state.schedule_task(
            f"data_lunch_{name}",
            callable,
            period=period,
            at=start_time,
        )


# Call for hydra
if __name__ == "__main__":
    run_app()

"""Data-Lunch package entrypoint."""

import hydra
import logging
import panel as pn

from omegaconf import DictConfig

from . import auth
from . import create_app, create_backend
from .scheduled_tasks import TaskManager

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# PANEL EXTENSIONS ------------------------------------------------------------
# Set panel extensions
log.debug("set extensions")
pn.extension(
    "tabulator",
    notifications=True,
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

    # Set auth configurations
    log.info("set auth context and encryption")
    auth_context = auth.AuthContext(config=config)
    # Auth encryption
    auth_context.set_app_auth_and_encryption()
    log.debug(
        f'authentication {"" if auth_context.is_auth_active() else "not "}active'
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
    authorize_callback_object: auth.AuthCallback = hydra.utils.instantiate(
        config.auth.authorization_callback, config
    )
    pn.config.authorize_callback = authorize_callback_object.authorize
    pn.config.auth_template = config.auth.auth_error_template

    # If basic auth is used the database and users credentials shall be created here
    if auth_context.is_basic_auth_active():
        log.info("initialize database and users credentials for basic auth")
        # Create tables
        auth_context.database_connector.create_database(
            add_basic_auth_users=auth_context.is_basic_auth_active(),
        )

    # Starting scheduled tasks
    log.info("start scheduled tasks")
    scheduled_tasks = hydra.utils.instantiate(config.panel.scheduled_tasks)
    scheduled_task_manager = TaskManager(config=config, tasks=scheduled_tasks)
    scheduled_task_manager.log_tasks(enabled_only=True)
    scheduled_task_manager.schedule_all()

    # Call the app factory function
    log.info("set config for app factory function")
    # Pass the create_app and create_backend function as a lambda function to
    # ensure that each invocation has a dedicated state variable (users'
    # selections are not shared between instances)
    # Backend exist only if auth is active
    # Health is an endpoint for app health assessments
    # Pass a dictionary for a multipage app
    pages = {"": lambda: create_app(config=config)}
    if auth_context.is_auth_active():
        pages["backend"] = lambda: create_backend(config=config)

    # If basic authentication is active, instantiate ta special auth object
    # otherwise leave an empty dict
    # This step is done before panel.serve because auth_provider requires that
    # the whole config is passed as an input
    if auth_context.is_basic_auth_active():
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


# Call for hydra
if __name__ == "__main__":
    run_app()

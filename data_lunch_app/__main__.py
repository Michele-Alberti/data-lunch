import datetime as dt
import hydra
import logging
import panel as pn
from typing import Callable
from omegaconf import DictConfig, OmegaConf
from omegaconf.errors import ConfigAttributeError
from . import auth
from . import create_app, create_backend

log = logging.getLogger(__name__)

# Set panel extensions
log.debug("set extensions")
pn.extension(
    "tabulator",
)


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def run_app(config: DictConfig):
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

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app and create_backend function as a lambda function to
    # ensure that each invocation has a dedicated state variable (users'
    # selections are not shared between instances)
    # Backend exist only if auth is active
    # Pass a dictionary for a multipage app
    pages = {"": lambda: create_app(config=config)}
    if auth.is_auth_active(config=config):
        pages["backend"] = lambda: create_backend(config=config)

    # If config.server.auth_provider exists, update
    # config.server.auth_provider key with the instantiated object
    try:
        auth_object = {
            "auth_provider": hydra.utils.instantiate(
                config.server.auth_provider, config
            )
        }
        log.debug(
            "auth_object dict set to instantiated object from config.server.auth_provider"
        )
    except ConfigAttributeError:
        auth_object = {}
        log.debug(
            "missing config.server.auth_provider, auth_object dict left empty"
        )

    # Mask the auth_provider key from config.server to avoid a TypeError
    # (multiple values for keyword argument 'auth_provider')
    masked_server_config = OmegaConf.masked_copy(
        config.server,
        [k for k in config.server.keys() if k != "auth_provider"],
    )

    pn.serve(panels=pages, **masked_server_config, **auth_object)


def schedule_task(
    name: str,
    enabled: bool,
    hour: int | None,
    minute: int | None,
    period: str,
    callable: Callable,
):
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

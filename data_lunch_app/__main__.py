import logging
import datetime as dt
import hydra
import panel as pn
from typing import Callable
from omegaconf import DictConfig
from . import auth
from . import create_app
from .core import delete_files, clean_tables

log = logging.getLogger(__name__)

# Set panel extensions
log.debug("set extensions")
pn.extension(
    "tabulator",
)


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def run_app(config: DictConfig):
    # Generate a random password
    guest_password = auth.generate_password(
        special_chars=config.panel.psw_special_chars
    )
    # Add hashed password to credentials file
    auth.add_user_hashed_password("guest", guest_password)

    # Starting scheduled cleaning
    if config.panel.scheduled_tasks:
        for task in config.panel.scheduled_tasks:
            schedule_task(
                **task.kwargs,
                callable=hydra.utils.instantiate(task.callable, config),
            )

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app function as a lambda function to ensure that each
    # invocation has a dedicated state variable (users' selections are not
    # shared between instances)
    pn.serve(
        lambda: create_app(config=config, guest_password=guest_password),
        auth_provider=hydra.utils.instantiate(config.auth),
        **config.server,
    )


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

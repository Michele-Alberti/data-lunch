import logging
import datetime as dt
import hydra
import panel as pn
from typing import Callable
from omegaconf import DictConfig
from . import create_app
from .core import delete_files, clean_tables

log = logging.getLogger(__name__)


@hydra.main(config_path="conf", config_name="config")
def run_app(config: DictConfig):

    # Starting scheduled cleaning
    schedule_task(
        config.panel.scheduled_tasks.scheduled_cleaning,
        lambda: clean_files_db(config),
    )

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app function as a lambda function to ensure that each
    # invocation has a dedicated state variable (users' selections are not
    # shared between instances)
    pn.serve(lambda: create_app(config), **config.server)


def schedule_task(task: DictConfig, function: Callable):
    # Starting scheduled tasks
    if task:
        log.info(f"starting task '{task.name}'")
        start_time = dt.datetime.today().replace(
            hour=task.hour,
            minute=task.minute,
        )
        # Set start time to tomorrow if the time already passed
        if start_time < dt.datetime.now():
            start_time = start_time + dt.timedelta(days=1)
        log.info(
            f"starting time: {start_time.strftime('%Y-%m-%d %H:%M')} - period: {task.period}"
        )
        pn.state.schedule_task(
            f"data_lunch_{task.name}",
            function,
            period=task.period,
            at=start_time,
        )


async def clean_files_db(config):
    log.info(f"clean task (files and db) executed at {dt.datetime.now()}")
    # Delete files
    delete_files(config)
    # Clean tables
    clean_tables(config)


# Call for hydra
if __name__ == "__main__":
    run_app()

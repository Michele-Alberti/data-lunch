import logging
import datetime as dt
import hydra
import panel as pn
from omegaconf import DictConfig
from . import create_app
from .core import delete_files, clean_tables

log = logging.getLogger(__name__)


@hydra.main(config_path="conf", config_name="config")
def run_app(config: DictConfig):

    # Starting scheduled tasks
    if config.panel.scheduled_cleaning:
        log.info("starting scheduled cleaning task")
        start_time = dt.datetime.today().replace(
            hour=config.panel.scheduled_cleaning.hour,
            minute=config.panel.scheduled_cleaning.minute,
        )
        # Set start time to tomorrow if the time already passed
        if start_time < dt.datetime.now():
            start_time = start_time + dt.timedelta(days=1)
        log.info(
            f"starting time: {start_time.strftime('%Y-%m-%d %H:%M')} - period: {config.panel.scheduled_cleaning.period}"
        )
        pn.state.schedule_task(
            "data_lunch_app_cleaning",
            lambda: clean_files_db(config),
            period=config.panel.scheduled_cleaning.period,
            at=start_time,
        )

    # Call the app factory function
    log.info("calling app factory function")
    # Pass the create_app function as a lambda function to ensure that each
    # invocation has a dedicated state variable (users' selections are not
    # shared between instances)
    pn.serve(lambda: create_app(config), **config.server)


async def clean_files_db(config):
    log.info(f"clean task (files and db) executed at {dt.datetime.now()}")
    # Delete files
    delete_files(config)
    # Clean tables
    clean_tables(config)


# Call for hydra
if __name__ == "__main__":
    run_app()

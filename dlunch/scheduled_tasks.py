"""Module with functions used to execute scheduled tasks.

See https://panel.holoviz.org/how_to/callbacks/schedule.html for details.
"""

import logging
import datetime as dt
from omegaconf import DictConfig
import panel as pn

from . import auth
from . import cloud
from . import core

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# CLASSES ---------------------------------------------------------------------
class TaskAction:
    """Generic task action object.

    Its scope is to build a callable that will be executed when the task is
    triggered.
    """

    def build_callable(self, config: DictConfig) -> callable:
        """Build and return the scheduled callable that executes a dummy
        task action.

        It just logs a message.

        Args:
            config (DictConfig): Hydra configuration dictionary.
        """

        async def action_callable() -> None:
            """Scheduled callable that executes a dummy task action."""
            log.info(
                f"dummy task executed for {config.panel.gui.title.lower()}"
            )

        return action_callable


class CleanFilesDB(TaskAction):
    """Task action for cleaning temporary tables and files.

    Its scope is to build a callable that will be executed when the task is
    triggered.
    """

    def build_callable(self, config: DictConfig) -> callable:
        """Build and return the scheduled callable that cleans temporary
        tables and files.

        Args:
            config (DictConfig): Hydra configuration dictionary.
        """

        # Set waiter
        waiter = core.Waiter(config=config)

        async def action_callable() -> None:
            """Scheduled callable that cleans temporary tables and files."""
            log.info(
                f"clean task (files and db) executed at {dt.datetime.now()}"
            )
            waiter.delete_files()
            waiter.clean_tables()

        return action_callable


class ResetGuestPassword(TaskAction):
    """Task action for resetting guest user password.

    Its scope is to build a callable that will be executed when the task is
    triggered.
    """

    def build_callable(self, config: DictConfig) -> callable:
        """Build and return the scheduled callable that resets the guest
        user password.

        Args:
            config (DictConfig): Hydra configuration dictionary.
        """

        # Set auth configurations
        auth_context = auth.AuthContext(config=config)

        async def action_callable() -> None:
            """Scheduled callable that resets the guest user password."""
            log.info(
                f"reset guest user password executed at {dt.datetime.now()}"
            )
            auth_context.database_connector.set_flag(
                id="reset_guest_user_password", value=True
            )
            auth_context.set_guest_user_password()

        return action_callable


class UploadDBToGCP(TaskAction):
    """Task action for uploading database to Google Cloud Storage.

    Its scope is to build a callable that will be executed when the task is
    triggered.

    Args:
        kwargs (dict): Keyword arguments for the cloud.upload_to_gcloud function.
    """

    def __init__(self, **kwargs) -> None:
        self.gcp_kwargs = kwargs

    def build_callable(self, config: DictConfig) -> callable:
        """Build and return the scheduled callable that uploads the database to
        Google Cloud Storage.

        Args:
            config (DictConfig): Hydra configuration dictionary.
        """

        async def action_callable() -> None:
            """Scheduled callable that uploads the database to Google Cloud Storage."""
            log.info(
                f"upload database to gcp storage executed at {dt.datetime.now()}"
            )
            cloud.upload_to_gcloud(**self.gcp_kwargs)

        return action_callable


class Task:
    """Generic task object.

    Args:
        name (str): Task name (used for logs).
        enabled (bool): Flag that marks a task as enabled.
        hour (int): Start hour (used only if also minute is not None).
        minute (int): Start minute (used only if also hour is not None).
        period (str): The period between executions.
            May be expressed as a timedelta or a string.

            * Week: `'1w'`
            * Day: `'1d'`
            * Hour: `'1h'`
            * Minute: `'1m'`
            * Second: `'1s'`
        actions (list[TaskAction]): List of actions to be executed.
    """

    def __init__(
        self,
        name: str,
        enabled: bool,
        hour: int | None,
        minute: int | None,
        period: str,
        actions: list[TaskAction],
    ) -> None:
        self.name: str = name
        """Task name (used for logs)."""
        self.enabled: bool = enabled
        """Flag that marks a task as enabled."""
        self.hour: int = hour
        """Start hour (used only if also minute is not None)."""
        self.minute: int = minute
        """Start minute (used only if also hour is not None)."""
        self.period: str = period
        """The period between executions.
            May be expressed as a timedelta or a string.

        * Week: `'1w'`
        * Day: `'1d'`
        * Hour: `'1h'`
        * Minute: `'1m'`
        * Second: `'1s'`
        """
        self.actions: list[TaskAction] = actions
        """List of actions to be executed."""

    def build_callable(self, config: DictConfig) -> callable:
        """Build and return a callable that executes all actions
        in the task.

        Args:
            config (DictConfig): Hydra configuration dictionary.
        """

        task_callables = [
            action.build_callable(config=config) for action in self.actions
        ]

        async def task_callable() -> None:
            for callable in task_callables:
                await callable()

        return task_callable

    def schedule_task(self, config: DictConfig) -> None:
        """Schedule a task execution using Panel.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        If start time is not defined, the task will start immediately.
        If hour and minute are defined, the task will start at the specified
        time. If the time already passed, the task will start the next day.
        """
        if self.enabled:
            log.info(f"starting task '{self.name}'")
            if (self.hour is not None) and (self.minute is not None):
                start_time = dt.datetime.today().replace(
                    hour=self.hour,
                    minute=self.minute,
                )
                if start_time < dt.datetime.now():
                    start_time = start_time + dt.timedelta(days=1)
                log.info(
                    f"starting time: {start_time.strftime('%Y-%m-%d %H:%M')} - period: {self.period}"
                )
            else:
                start_time = None
                log.info(f"starting time: now - period: {self.period}")

            # Schedule task
            pn.state.schedule_task(
                name=self.name,
                callback=self.build_callable(config),
                period=self.period,
                at=start_time,
            )


class TaskManager:
    """Task manager object.

    Used to schedule all tasks given a list of tasks.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        tasks (list[Task]): List of tasks to be scheduled.
    """

    def __init__(self, config: DictConfig, tasks: list[Task]) -> None:
        self.config: DictConfig = config
        """Hydra configuration dictionary."""
        self.tasks: list[Task] = tasks
        """List of tasks to be scheduled."""

    def log_tasks(self, enabled_only: bool = False) -> None:
        """Log all tasks defined in the collection.

        Args:
            enabled_only (bool): If True, only enabled tasks will be listed.
        """
        message = "listing tasks"
        if enabled_only:
            message += " (enabled only)"

        # Loop over tasks and actions
        for task in self.tasks:
            if enabled_only and not task.enabled:
                continue
            message += f"\ntask: {task.name}"
            message += (
                "\n"
                if enabled_only
                else f" ({'enabled' if task.enabled else 'disabled'})\n"
            )
            message += "  actions:"
            for action in task.actions:
                message += f"\n    {action.__class__.__name__}"

        log.info(message)

    def schedule_all(self) -> None:
        """Schedule all tasks in the collection."""
        for task in self.tasks:
            task.schedule_task(self.config)


# FUNCTIONS -------------------------------------------------------------------
# Intentionally left empty

# App metadata
__version__ = "1.6.1"

import pathlib
import hydra
import logging
import panel as pn
import param
import panel.widgets as pnw
import pandas as pd
from panel.widgets import Tqdm
from pathlib import Path
import sqlalchemy
from omegaconf import DictConfig, open_dict

# Database imports
from .models import db, create_database
from .cloud import download_from_gcloud

# Core imports
from . import core

log = logging.getLogger(__name__)


# UTILITY FUNCTIONS -----------------------------------------------------------
def on_session_destroyed(config: DictConfig, session_context):

    # If google cloud is configured, upload the sqlite database to storage
    # bucket
    if config.db.gcloud_storage:
        log.info("uploading database file to bucket")
        hydra.utils.call(config.db.gcloud_storage.upload)


# APP FACTORY FUNCTION --------------------------------------------------------


def create_app(config: DictConfig) -> pn.Template:
    """Panel app factory function"""

    log.info("starting initialization process")

    log.debug("create 'shared_data' folder")
    pathlib.Path(config.db.shared_data_folder).mkdir(exist_ok=True)

    log.info("initialize database")
    # If configured, download the sqlite database from google cloud bucket
    if config.db.gcloud_storage:
        log.info("downloading database file from bucket")
        hydra.utils.call(config.db.gcloud_storage.download)
    # Then create tables
    create_database(config)

    log.info("instantiate Panel app")

    # Panel configurations
    log.debug("set threads number")
    pn.config = config.panel.nthreads

    # Set action to run when sessions are destroyed
    # If google cloud is configured, download the sqlite database from storage
    # bucket
    if config.db.gcloud_storage:
        log.debug("set 'on_session_destroy' actions")
        pn.state.on_session_destroyed(
            lambda context: on_session_destroyed(config, context)
        )

    # DASHBOARD BASE TEMPLATE
    # Create web app template
    app = pn.template.VanillaTemplate(
        title="Data Lunch", sidebar_width=core.sidebar_width
    )

    # RESULTS (USED IN MAIN SECTION)
    # Create column for resulting menus
    res_col = pn.Column()

    # BASE INSTANCES
    # Create person instance
    person = core.Person(config, name="User")
    # Create dataframe instance
    dataframe = pnw.Tabulator(name="Order")
    # Update dataframe widget
    core.reload_menu("", config, dataframe, res_col)

    # MODAL
    error_message = pn.pane.HTML(
        style={"color": "red", "font-weight": "bold"},
        sizing_mode="stretch_width",
    )
    error_message.visible = False
    confirm_message = pn.pane.HTML(
        style={"color": "green", "font-weight": "bold"},
        sizing_mode="stretch_width",
    )
    confirm_message.visible = False

    # SIDEBAR
    # Widgets
    person_widget = pn.Param(person.param, width=core.sidebar_width)
    file_widget = pnw.FileInput(accept=".png,.jpg,.xlsx")
    # Build menu button
    build_menu_button = pnw.Button(
        name="Build Menu", button_type="primary", sizing_mode="stretch_width"
    )
    build_menu_button.on_click(
        lambda e: core.build_menu(
            e,
            config,
            app,
            file_widget,
            dataframe,
            res_col,
            [error_message, confirm_message],
        )
    )
    # Create download button
    download_button = pn.widgets.FileDownload(
        callback=lambda: core.download_dataframe(
            config, app, [error_message, confirm_message]
        ),
        filename=config.panel.file_name + ".xlsx",
    )
    # Sidebar tabs
    person_text = """
    ### User Data
    Fill your name (use unique values) and select the lunch time.<br>
    Click "Delete Order" to remove your orders.
    """
    upload_text = """
    ### Menu Upload
    Select a .png, .jpg or .xlsx file with the menu.<br>
    The app may add some default items to the menu.

    **For .xlsx:** list menu items starting from cell A1, one per each row.
    """
    download_text = """
    ### Download Orders
    Download the orders list.
    """
    sidebar_tabs = pn.Tabs(
        pn.Column(person_text, person_widget, name="User"),
        pn.Column(
            upload_text,
            file_widget,
            build_menu_button,
            name="Menu Upload",
        ),
        pn.Column(download_text, download_button, name="Download Orders"),
    )

    # MAIN
    # Create refresh button
    refresh_button = pnw.Button(name="Refresh")
    refresh_button.on_click(
        lambda e: core.reload_menu(e, config, dataframe, res_col)
    )
    # Create send button
    send_order_button = pnw.Button(
        name="Send", button_type="primary", sizing_mode="stretch_width"
    )
    send_order_button.on_click(
        lambda e: core.send_order(
            e,
            config,
            app,
            person,
            dataframe,
            res_col,
            [error_message, confirm_message],
        )
    )
    # Create delete order
    delete_order_button = pnw.Button(
        name="Delete Order", button_type="danger", sizing_mode="stretch_width"
    )
    delete_order_button.on_click(
        lambda e: core.delete_order(
            e,
            config,
            app,
            person,
            dataframe,
            res_col,
            [error_message, confirm_message],
        )
    )

    # Build dashboard
    app.sidebar.append(sidebar_tabs)
    app.main.append(
        pn.Column(
            "# Menu",
            refresh_button,
            pn.Spacer(height=25),
            dataframe,
            pn.Spacer(height=25),
            pn.Row(send_order_button, delete_order_button),
            res_col,
        )
    )
    app.modal.append(error_message)
    app.modal.append(confirm_message)

    app.servable()

    log.info("initialization process completed")

    return app

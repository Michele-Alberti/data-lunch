# App metadata
__version__ = "1.0.1"

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

# Core imports
from . import core

log = logging.getLogger(__name__)

# APP FACTORY FUNCTION --------------------------------------------------------


def create_app(config: DictConfig) -> pn.Template:
    """Panel app factory function"""

    log.info("starting initialization process")

    log.debug("create 'shared_data' folder")
    pathlib.Path(config.panel.shared_data_folder).mkdir(exist_ok=True)

    log.debug("initialize database")
    create_database(config)

    log.debug("instantiate Panel app")

    # Panel configurations
    log.debug("set threads number")
    pn.config = config.panel.nthreads

    # DASHBOARD BASE TEMPLATE
    # Create web app template
    app = pn.template.VanillaTemplate(
        title="Data Lunch", sidebar_width=core.sidebar_width
    )

    # BASE INSTANCES
    # Create person instance
    person = core.Person(name="User")
    # Create dataframe instance
    dataframe = pnw.Tabulator(name="Order")
    # Update dataframe widget
    core.reload_menu("", config, dataframe)

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
    menu_image_widget = pnw.FileInput()
    # Build menu button
    build_menu_button = pnw.Button(
        name="Build Menu", button_type="primary", sizing_mode="stretch_width"
    )
    build_menu_button.on_click(
        lambda e: core.build_menu(
            e,
            config,
            app,
            menu_image_widget,
            dataframe,
            [error_message, confirm_message],
        )
    )
    # Create download button
    download_button = pn.widgets.FileDownload(
        callback=lambda: core.download_dataframe(
            config, app, dataframe, [error_message, confirm_message]
        ),
        filename=config.panel.file_name,
    )
    # Sidebar tabs
    upload_text = """
    ### Menu Upload
    Select a .png file with the menu.
    """
    download_text = """
    ### Download Orders
    Download the orders list.
    """
    sidebar_tabs = pn.Tabs(
        person_widget,
        pn.Column(
            upload_text,
            menu_image_widget,
            build_menu_button,
            name="Menu Upload",
        ),
        pn.Column(download_text, download_button, name="Download Orders"),
    )

    # MAIN
    # Create refresh button
    refresh_button = pnw.Button(name="Refresh")
    refresh_button.on_click(lambda e: core.reload_menu(e, config, dataframe))
    # Create send button
    send_order_button = pnw.Button(
        name="Send", button_type="primary", sizing_mode="stretch_width"
    )
    send_order_button.on_click(
        lambda e: core.send_order(
            e, config, app, person, dataframe, [error_message, confirm_message]
        )
    )

    # Build dashboard
    app.sidebar.append(sidebar_tabs)
    app.main.append(pn.Column(refresh_button, dataframe, send_order_button))
    # app.modal.append(page_tqdm)
    # app.modal.append(ads_tqdm)
    app.modal.append(error_message)
    app.modal.append(confirm_message)

    app.servable()

    log.info("initialization process completed")

    return app

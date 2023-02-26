# App metadata
__version__ = "1.17.0"

import pathlib
import hydra
import logging
import panel as pn
from omegaconf import DictConfig, open_dict

# Database imports
from . import models
from .cloud import download_from_gcloud

# Core imports
from . import core

# Graphic interface imports
from . import gui

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
    models.create_database(config)

    log.info("instantiate Panel app")

    # Panel configurations
    log.debug("set panel config and flags")
    # Configurations
    pn.config.nthreads = config.panel.nthreads
    pn.config.notifications = True
    # Set the no_more_orders flag if it is None (not found in flags table)
    session = models.create_session(config)
    if models.get_flag(session=session, id="no_more_orders") is None:
        models.set_flag(session=session, id="no_more_orders", value=False)

    # Set action to run when sessions are destroyed
    # If google cloud is configured, download the sqlite database from storage
    # bucket
    if config.db.gcloud_storage:
        log.debug("set 'on_session_destroy' actions")
        pn.state.on_session_destroyed(
            lambda context: on_session_destroyed(config, context)
        )

    pn.extension(raw_css=[gui.sidenav_css, gui.tabulator_css, gui.button_css])

    # DASHBOARD BASE TEMPLATE
    log.debug("instantiate base template")
    # Create web app template
    app = pn.template.VanillaTemplate(
        title=config.panel.title,
        sidebar_width=gui.sidebar_width,
        favicon=config.panel.favicon_path,
    )

    # Set panel extensions
    log.debug("set extensions")
    pn.extension(css_files=gui.css_files, js_files=gui.js_files)

    # CONFIGURABLE OBJECTS
    # Since Person class need the config variable for initialization, every
    # graphic element that require the Person class has to be instantiated
    # by a dedicated function
    # Create person instance, widget and column
    log.debug("instantiate person class and graphic elements")
    person = gui.Person(config, name="User")
    person_widget = pn.Param(person.param, width=gui.sidebar_width)
    person_column = pn.Column(
        gui.person_text, person_widget, name="User", width=gui.sidebar_width
    )
    log.debug("replace person column placeholder")
    gui.sidebar_tabs.objects[0] = person_column

    # DEFINE CALLBACKS
    log.debug("define main section callbacks")
    gui.define_main_section_callbacks(config, app, person)
    log.debug("define sidebar section callbacks")
    gui.define_sidebar_section_callbacks(config, app)

    # DASHBOARD
    # Build dashboard
    app.sidebar.append(gui.sidebar_tabs)
    app.main.append(gui.no_more_order_text)
    app.main.append(
        pn.Row(
            "# Menu",
            pn.layout.HSpacer(),
            gui.refresh_button,
        ),
    )
    app.main.append(gui.quote)
    app.main.append(pn.Spacer(height=15))
    app.main.append(gui.menu_flexbox)
    app.main.append(gui.buttons_flexbox)
    app.main.append(pn.layout.Divider(sizing_mode="stretch_width"))
    app.main.append(gui.res_col)
    app.modal.append(gui.error_message)
    app.modal.append(gui.confirm_message)

    # Set components visibility based on no_more_order_button state
    # and reload menu
    core.reload_menu(
        None,
        config,
    )
    gui.reload_on_no_more_order(
        models.get_flag(session=session, id="no_more_orders"), config
    )

    # Close database session
    session.close()

    app.servable()

    log.info("initialization process completed")

    return app

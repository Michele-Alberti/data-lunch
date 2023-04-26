# App metadata
__version__ = "1.20.1"

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


# APP FACTORY FUNCTION --------------------------------------------------------


def create_app(config: DictConfig) -> pn.Template:
    """Panel app factory function"""

    log.info("starting initialization process")

    log.debug("create 'shared_data' folder")
    pathlib.Path(config.db.shared_data_folder).mkdir(exist_ok=True)

    log.info("initialize database")
    # Create tables
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

    # DASHBOARD BASE TEMPLATE
    log.debug("instantiate base template")
    # Create web app template
    app = pn.template.VanillaTemplate(
        title=config.panel.gui.title,
        sidebar_width=gui.sidebar_width,
        favicon=config.panel.gui.favicon_path,
        logo=config.panel.gui.logo_path,
    )

    # Set panel extensions
    log.debug("set extensions")
    pn.extension(
        css_files=gui.css_files,
        raw_css=gui.raw_css_list,
        js_files=gui.js_files,
    )

    # CONFIGURABLE OBJECTS
    # Since Person class need the config variable for initialization, every
    # graphic element that require the Person class has to be instantiated
    # by a dedicated function
    # Create person instance, widget and column
    log.debug("instantiate person class and graphic graphic interface")
    person = gui.Person(config, name="User")
    gi = gui.GraphicInterface(config, app, person)

    # DASHBOARD
    # Build dashboard (the header object is used if defined)
    if config.panel.gui.header_object:
        app.header.append(gi.header_object)
    app.sidebar.append(gi.sidebar_tabs)
    app.main.append(gi.no_more_order_text)
    app.main.append(gi.main_header_row)
    app.main.append(gi.quote)
    app.main.append(pn.Spacer(height=15))
    app.main.append(gi.menu_flexbox)
    app.main.append(gi.buttons_flexbox)
    app.main.append(pn.layout.Divider(sizing_mode="stretch_width"))
    app.main.append(gi.res_col)
    app.modal.append(gi.error_message)
    app.modal.append(gi.confirm_message)

    # Set components visibility based on no_more_order_button state
    # and reload menu
    core.reload_menu(
        None,
        config,
        gi,
    )
    gi.reload_on_no_more_order(
        models.get_flag(session=session, id="no_more_orders")
    )

    # Close database session
    session.close()

    app.servable()

    log.info("initialization process completed")

    return app

# App metadata
__version__ = "3.0.0"

import importlib.resources
import pathlib
import hydra
import logging
import panel as pn
from omegaconf import DictConfig, OmegaConf

# Database imports
from . import models

# Other Data-Lunch imports
from . import core
from . import gui
from . import auth
from .auth import pn_user

log = logging.getLogger(__name__)

# OMEGACONF RESOLVER ----------------------------------------------------------
OmegaConf.register_new_resolver(
    "pkg_path", lambda pkg: str(importlib.resources.files(pkg))
)


# APP FACTORY FUNCTION --------------------------------------------------------


def create_app(config: DictConfig) -> pn.Template:
    """Panel app factory function"""
    log.info("starting initialization process")

    log.info("initialize database")
    # Create tables
    models.create_database(
        config, add_basic_auth_users=auth.is_basic_auth_active(config=config)
    )

    log.info("initialize support variables")
    # Generate a random password only if requested (check on flag)
    log.debug("config guest user")
    guest_password = core.set_guest_user_password(config)

    log.info("instantiate app")

    # Panel configurations
    log.debug("set toggles initial state")
    # Set the no_more_orders flag if it is None (not found in flags table)
    if models.get_flag(config=config, id="no_more_orders") is None:
        models.set_flag(config=config, id="no_more_orders", value=False)
    # Set guest override flag if it is None (not found in flags table)
    # Guest override flag is per-user and is not set for guests
    if (
        models.get_flag(config=config, id=f"{pn_user(config)}_guest_override")
        is None
    ) and not auth.is_guest(
        user=pn_user(config), config=config, allow_override=False
    ):
        models.set_flag(
            config=config, id=f"{pn_user(config)}_guest_override", value=False
        )

    # DASHBOARD BASE TEMPLATE
    log.debug("instantiate base template")
    # Create web app template
    app = pn.template.VanillaTemplate(
        title=config.panel.gui.title,
        sidebar_width=gui.sidebar_width,
        favicon=config.panel.gui.favicon_path,
        logo=config.panel.gui.logo_path,
        css_files=OmegaConf.to_container(
            config.panel.gui.template_css_files, resolve=True
        ),
        raw_css=OmegaConf.to_container(
            config.panel.gui.template_raw_css, resolve=True
        ),
    )

    # CONFIGURABLE OBJECTS
    # Since Person class need the config variable for initialization, every
    # graphic element that require the Person class has to be instantiated
    # by a dedicated function
    # Create person instance, widget and column
    log.debug("instantiate person class and graphic graphic interface")
    person = gui.Person(config, name="User")
    gi = gui.GraphicInterface(config, app, person, guest_password)

    # DASHBOARD
    # Build dashboard (the header object is used if defined)
    app.header.append(gi.header_row)
    app.sidebar.append(gi.sidebar_tabs)
    app.main.append(gi.no_menu_col)
    app.main.append(gi.guest_override_alert)
    app.main.append(gi.no_more_order_alert)
    app.main.append(gi.main_header_row)
    app.main.append(gi.quote)
    app.main.append(pn.Spacer(height=15))
    app.main.append(gi.menu_flexbox)
    app.main.append(gi.buttons_flexbox)
    app.main.append(gi.results_divider)
    app.main.append(gi.res_col)
    app.modal.append(gi.error_message)
    app.modal.append(gi.confirm_message)

    # Set components visibility based on no_more_order_button state
    # and reload menu
    gi.reload_on_no_more_order(
        toggle=models.get_flag(config=config, id="no_more_orders"),
        reload=False,
    )
    gi.reload_on_guest_override(
        toggle=models.get_flag(
            config=config,
            id=f"{pn_user(config)}_guest_override",
            value_if_missing=False,
        ),
        reload=False,
    )
    core.reload_menu(
        None,
        config,
        gi,
    )

    app.servable()

    log.info("initialization process completed")

    return app


def create_backend(config: DictConfig) -> pn.Column:
    """Panel app factory function"""

    log.info("starting initialization process")

    log.info("initialize database")
    # Create tables
    models.create_database(
        config, add_basic_auth_users=auth.is_basic_auth_active(config=config)
    )

    log.info("instantiate backend")

    # DASHBOARD
    log.debug("instantiate base template")
    # Create web app template
    backend = pn.template.VanillaTemplate(
        title=f"{config.panel.gui.title} Backend",
        favicon=config.panel.gui.favicon_path,
        logo=config.panel.gui.logo_path,
        css_files=OmegaConf.to_container(
            config.panel.gui.template_css_files, resolve=True
        ),
        raw_css=OmegaConf.to_container(
            config.panel.gui.template_raw_css, resolve=True
        ),
    )

    # CONFIGURABLE OBJECTS
    backend_gi = gui.BackendInterface(config)

    # DASHBOARD
    # Build dashboard
    backend.header.append(backend_gi.header_row)
    backend.main.append(backend_gi.backend_controls)

    backend.servable()

    log.info("initialization process completed")

    return backend

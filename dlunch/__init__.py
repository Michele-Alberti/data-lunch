"""Main Data-Lunch package."""

import importlib.resources
import logging
import panel as pn
from omegaconf import DictConfig, OmegaConf

# Relative imports
from .core import __version__, Waiter
from . import gui
from .auth import AuthUser

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# OMEGACONF RESOLVER ----------------------------------------------------------
OmegaConf.register_new_resolver(
    "pkg_path", lambda pkg: str(importlib.resources.files(pkg))
)

# APP FACTORY FUNCTION --------------------------------------------------------


def create_app(config: DictConfig) -> pn.Template:
    """Panel main app factory function

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        pn.Template: Panel main app template.
    """
    log.info("starting initialization process")

    # Create an instance of AuthUser (that includes an instance of AuthContext)
    # and a waiter instance
    auth_user = AuthUser(config=config)
    waiter = Waiter(config=config)

    log.info("initialize database")
    # Create tables
    waiter.database_connector.create_database(
        add_basic_auth_users=auth_user.auth_context.is_basic_auth_active(),
    )

    log.info("initialize support variables")
    # Generate a random password only if requested (check on flag)
    log.debug("config guest user")
    guest_password = auth_user.auth_context.set_guest_user_password()

    log.info("instantiate app")

    # Panel configurations
    log.debug("set toggles initial state")
    # Set the no_more_orders flag if it is None (not found in flags table)
    if waiter.database_connector.get_flag(id="no_more_orders") is None:
        waiter.database_connector.set_flag(id="no_more_orders", value=False)
    # Set guest override flag if it is None (not found in flags table)
    # Guest override flag is per-user and is not set for guests
    if (
        waiter.database_connector.get_flag(
            id=f"{auth_user.name}_guest_override"
        )
        is None
    ) and not auth_user.is_guest():
        waiter.database_connector.set_flag(
            id=f"{auth_user.name}_guest_override", value=False
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
    log.debug("instantiate person class and graphic interface")
    gi = gui.GraphicInterface(
        config=config,
        waiter=waiter,
        app=app,
        guest_password=guest_password,
        auth_user=auth_user,
    )

    # DASHBOARD
    # Build dashboard (the header object is used if defined)
    app.header.append(gi.header_row)
    app.sidebar.append(gi.sidebar_tabs)
    app.main.append(gi.no_menu_col)
    app.main.append(gi.guest_override_alert)
    app.main.append(gi.no_more_order_alert)
    app.main.append(gi.missing_birthday_alert)
    app.main.append(gi.main_header_row)
    app.main.append(gi.quote)
    app.main.append(pn.Spacer(height=15))
    app.main.append(gi.menu_flexbox)
    app.main.append(gi.buttons_flexbox)
    app.main.append(gi.results_divider)
    app.main.append(gi.res_col)
    app.modal.append(gi.error_message)

    # Set components visibility based on no_more_order_button state
    # and reload menu
    gi.reload_on_no_more_order(
        toggle=waiter.database_connector.get_flag(id="no_more_orders"),
        reload=False,
    )
    gi.reload_on_guest_override(
        toggle=waiter.database_connector.get_flag(
            id=f"{auth_user.name}_guest_override",
            value_if_missing=False,
        ),
        reload=False,
    )
    waiter.reload_menu(
        None,
        gi,
    )

    app.servable()

    log.info("initialization process completed")

    return app


def create_backend(config: DictConfig) -> pn.Template:
    """Panel backend app factory function

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        pn.Template: Panel backend app template.
    """

    log.info("starting initialization process")

    # Create an instance of AuthUser (which has also an instance of AuthContext
    # among its attributes)
    auth_user = AuthUser(config=config)

    log.info("initialize database")
    # Create tables
    auth_user.auth_context.database_connector.create_database(
        add_basic_auth_users=auth_user.auth_context.is_basic_auth_active(),
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
    backend_gi = gui.BackendInterface(config, auth_user=auth_user)

    # DASHBOARD
    # Build dashboard
    backend.header.append(backend_gi.header_row)
    backend.main.append(backend_gi.backend_controls)

    backend.servable()

    log.info("initialization process completed")

    return backend

# App metadata
__version__ = "1.14.0"

import datetime
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

# QUOTES ----------------------------------------------------------------------
# Quote table
quotes_filename = pathlib.Path(__file__).parent / "quotes.xlsx"
df_quotes = pd.read_excel(quotes_filename)
# Quote of the day
seed_day = int(datetime.datetime.today().strftime("%Y%m%d"))
df_quote = df_quotes.sample(n=1, random_state=seed_day)

# CSS FILES -------------------------------------------------------------------
# CSS
# Font awesome icons
css_fa_icons_files = [
    pathlib.Path(__file__).parent
    / "static"
    / "fontawesome"
    / "css"
    / "fontawesome.css",
    pathlib.Path(__file__).parent
    / "static"
    / "fontawesome"
    / "css"
    / "brands.css",
    pathlib.Path(__file__).parent
    / "static"
    / "fontawesome"
    / "css"
    / "solid.css",
]
css_fa_icons_files = [str(file) for file in css_fa_icons_files]


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
    log.debug("set panel config and cache")
    # Configurations
    pn.config.nthreads = config.panel.nthreads
    pn.config.notifications = True
    # Cache for no_more_orders flag
    if "no_more_orders" not in pn.state.cache:
        pn.state.cache["no_more_orders"] = False

    # Set action to run when sessions are destroyed
    # If google cloud is configured, download the sqlite database from storage
    # bucket
    if config.db.gcloud_storage:
        log.debug("set 'on_session_destroy' actions")
        pn.state.on_session_destroyed(
            lambda context: on_session_destroyed(config, context)
        )

    # CUSTOM CSS
    sidenav_css = """
    .sidenav {
        overflow-y: auto !important;
    }

    #sidebar {
        padding-right: 12px !important;
    }
    """
    tabulator_css = """
    .sidenav .tabulator .tabulator-header .tabulator-col .tabulator-col-content .tabulator-col-title {
        white-space: normal;
        text-overflow: clip;
    }

    .sidenav .tabulator {
        border: 1.5px solid lightgray;
    }
    """
    button_css = """
    .refresh-button .bk-btn-group button {
        font-size: 2rem;
        vertical-align: middle;
        padding: 0;
        margin: 0;
        line-height: 1.25rem;
        border-style: none;
    }
    """
    pn.extension(raw_css=[sidenav_css, tabulator_css, button_css])

    # DASHBOARD BASE TEMPLATE
    # Create web app template
    app = pn.template.VanillaTemplate(
        title="Data Lunch", sidebar_width=core.sidebar_width
    )
    # Add fontawesome icons
    pn.extension(css_files=css_fa_icons_files)

    # QUOTE OF THE DAY
    quote = pn.pane.Markdown(
        f"""
        _{df_quote.quote.iloc[0]}_

        **{df_quote.author.iloc[0]}**
        """
    )
    # RESULTS (USED IN MAIN SECTION)
    # Create column for statistics
    stats_col = pn.Column(name="Stats", width=core.sidebar_width)
    # Create column for lunch time labels
    time_col = pn.Column(width=125)
    # Create column for resulting menus
    res_col = pn.Column()
    # Toggle button that stop orders (used in time column)
    toggle_no_more_order_button = pnw.Toggle(
        value=pn.state.cache["no_more_orders"],
        name="⌛ Stop Orders",
        width=150,
    )

    # Callback on every "toggle" action
    @pn.depends(toggle_no_more_order_button, watch=True)
    def reload_on_no_more_order(toggle_button):

        # Update global variable
        pn.state.cache["no_more_orders"] = toggle_button

        # Show "no more order" text
        no_more_order_text.visible = toggle_button

        # Deactivate send order and delete order buttons
        send_order_button.disabled = toggle_button
        delete_order_button.disabled = toggle_button

        # Simply reload the menu when the toggle button value changes
        core.reload_menu(
            "",
            config,
            dataframe,
            stats_col,
            res_col,
            time_col,
            toggle_no_more_order_button,
        )

    # BASE INSTANCES
    # Create person instance
    person = core.Person(config, name="User")
    # Create dataframe instance
    dataframe = pnw.Tabulator(name="Order")

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
    file_widget = pnw.FileInput(accept=".png,.jpg,.jpeg,.xlsx")
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
            stats_col,
            res_col,
            time_col,
            toggle_no_more_order_button,
            [error_message, confirm_message],
        )
    )
    # Create download button
    download_button = pn.widgets.FileDownload(
        callback=lambda: core.download_dataframe(
            config, app, dataframe, [error_message, confirm_message]
        ),
        filename=config.panel.file_name + ".xlsx",
    )
    # Sidebar tabs
    person_text = """
    ### User Data
    Fill your name (duplicates are not allowed) and select the lunch time.<br>
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
    Download the order list.
    """
    sidebar_tabs = pn.Tabs(
        pn.Column(
            person_text, person_widget, name="User", width=core.sidebar_width
        ),
        pn.Column(
            upload_text,
            file_widget,
            build_menu_button,
            name="Menu Upload",
            width=core.sidebar_width,
        ),
        pn.Column(
            download_text,
            download_button,
            name="Download Orders",
            width=core.sidebar_width,
        ),
        stats_col,
        width=core.sidebar_width,
    )

    # MAIN
    # Create the "no more order" message
    no_more_order_text = pn.pane.HTML(
        """
        <div style="font-size: 1.25rem; color: crimson; background-color: whitesmoke; border-left: 0.5rem solid crimson; padding: 0.5rem">
            <i class="fa-solid fa-circle-exclamation fa-fade" style="--fa-animation-duration: 1.5s;"></i> <strong>Oh no! You missed this train...</strong><br>
            Orders are closed, better luck next time.
        </div>
        """,
        margin=5,
        sizing_mode="stretch_width",
    )
    # Create refresh button
    # Text is centered thanks to CSS extension via pn.extension (see above)
    refresh_button = pnw.Button(
        name="⟲",
        width=45,
        height=45,
        align=("end", "start"),
        css_classes=["refresh-button"],
    )
    refresh_button.on_click(
        lambda e: core.reload_menu(
            e,
            config,
            dataframe,
            stats_col,
            res_col,
            time_col,
            toggle_no_more_order_button,
        )
    )
    # Create send button
    send_order_button = pnw.Button(
        name="✔ Send Order", button_type="primary", width=150
    )
    send_order_button.on_click(
        lambda e: core.send_order(
            e,
            config,
            app,
            person,
            dataframe,
            stats_col,
            res_col,
            time_col,
            toggle_no_more_order_button,
            [error_message, confirm_message],
        )
    )
    # Create delete order
    delete_order_button = pnw.Button(
        name="✖ Delete Order", button_type="danger", width=150
    )
    delete_order_button.on_click(
        lambda e: core.delete_order(
            e,
            config,
            app,
            person,
            dataframe,
            stats_col,
            res_col,
            time_col,
            toggle_no_more_order_button,
            [error_message, confirm_message],
        )
    )

    # Create flexboxes
    menu_flexbox = pn.FlexBox(
        *[dataframe, time_col], sizing_mode="stretch_height"
    )
    buttons_flexbox = pn.FlexBox(
        *[send_order_button, toggle_no_more_order_button, delete_order_button]
    )

    # DASHBOARD
    # Build dashboard
    app.sidebar.append(sidebar_tabs)
    app.main.append(no_more_order_text)
    app.main.append(
        pn.Row(
            "# Menu",
            pn.layout.HSpacer(),
            refresh_button,
        ),
    )
    app.main.append(quote)
    app.main.append(pn.Spacer(height=15))
    app.main.append(menu_flexbox)
    app.main.append(buttons_flexbox)
    app.main.append(pn.layout.Divider(sizing_mode="stretch_width"))
    app.main.append(res_col)
    app.modal.append(error_message)
    app.modal.append(confirm_message)

    # Set components visibility based on no_more_order_button state
    # and reload menu
    reload_on_no_more_order(pn.state.cache["no_more_orders"])

    app.servable()

    log.info("initialization process completed")

    return app

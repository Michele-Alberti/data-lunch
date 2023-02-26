import datetime
import logging
from omegaconf import DictConfig
import pandas as pd
import panel as pn
import panel.widgets as pnw
import param
import pathlib
import random

# Database imports
from . import models

# Core imports
from . import core

log = logging.getLogger(__name__)


# OPTIONS AND DEFAULTS --------------------------------------------------------
# App
sidebar_width = 400
# Unicode Emoji fro food
food_emoji = [
    "&#127858;",
    "&#127791;",
    "&#127790;",
    "&#127789;",
    "&#129391;",
    "&#127829;",
    "&#127830;",
    "&#127828;",
    "&#129386;",
    "&#127831;",
    "&#129367;",
    "&#129369;",
    "&#127839;",
    "&#129385;",
    "&#129365;",
    "&#129382;",
    "&#129388;",
    "&#129384;",
    "&#129379;",
    "&#129377;",
    "&#127857;",
    "&#127837;",
    "&#127836;",
]


# CLASS -----------------------------------------------------------------------
class Person(param.Parameterized):
    username = param.String(default="", doc="your name")
    lunch_time = param.ObjectSelector(
        default="12:30", doc="orario", objects=["12:30"]
    )
    guest = param.Boolean(default=False, doc="guest flag")
    note = param.String(default="", doc="note")

    def __init__(self, config, **params):
        super().__init__(**params)
        self.param["lunch_time"].objects = config.panel.lunch_times_options

    def __str__(self):
        return f"PERSON:{self.name}"


# QUOTES ----------------------------------------------------------------------
# Quote table
quotes_filename = pathlib.Path(__file__).parent / "quotes.xlsx"
df_quotes = pd.read_excel(quotes_filename)
# Quote of the day
seed_day = int(datetime.datetime.today().strftime("%Y%m%d"))
df_quote = df_quotes.sample(n=1, random_state=seed_day)


# CSS FILES -------------------------------------------------------------------
css_files = []


# CUSTOM CSS ------------------------------------------------------------------
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

.tabulator {
    border: 1.5px solid lightgray !important;
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


# STATIC TEXTS ----------------------------------------------------------------
# "no more order" message
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
# Tabs section text
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

# JS FILES --------------------------------------------------------------------
# Font awesome icons
js_files = {"fa-icon": "https://kit.fontawesome.com/377fe96f85.js"}


# MAIN SECTION ----------------------------------------------------------------
# Elements required for build the main section of the web app

# WIDGETS
# Quote of the day
quote = pn.pane.Markdown(
    f"""
    _{df_quote.quote.iloc[0]}_

    **{df_quote.author.iloc[0]}**
    """
)
# Create dataframe instance
dataframe = pnw.Tabulator(name="Order")

# BUTTONS
# Create refresh button
# Text is centered thanks to CSS extension via pn.extension (see above)
refresh_button = pnw.Button(
    name="⟲",
    width=45,
    height=45,
    align=("end", "start"),
    css_classes=["refresh-button"],
)
# Create send button
send_order_button = pnw.Button(
    name="✔ Send Order", button_type="primary", width=150
)
# Create toggle button that stop orders (used in time column)
# Initialized to False, but checked on app creation
toggle_no_more_order_button = pnw.Toggle(
    value=False,
    name="⌛ Stop Orders",
    width=150,
)
# Create delete order
delete_order_button = pnw.Button(
    name="✖ Delete Order", button_type="danger", width=150
)

# COLUMNS
# Create column for lunch time labels
time_col = pn.Column(width=125)
# Create column for resulting menus
res_col = pn.Column(sizing_mode="stretch_width")

# FLEXBOXES
menu_flexbox = pn.FlexBox(*[dataframe, time_col], sizing_mode="stretch_height")
buttons_flexbox = pn.FlexBox(
    *[send_order_button, toggle_no_more_order_button, delete_order_button]
)


# CALLBACKS
def reload_on_no_more_order(toggle_button: pnw.Toggle, config: DictConfig):
    # Update global variable
    session = models.create_session(config)
    models.set_flag(session=session, id="no_more_orders", value=toggle_button)

    # Show "no more order" text
    no_more_order_text.visible = toggle_button

    # Deactivate send order and delete order buttons
    send_order_button.disabled = toggle_button
    delete_order_button.disabled = toggle_button

    # Simply reload the menu when the toggle button value changes
    core.reload_menu(
        None,
        config,
    )


def define_main_section_callbacks(
    config: DictConfig, app: pn.Template, person: Person
):
    # Refresh button callback
    refresh_button.on_click(
        lambda e: core.reload_menu(
            e,
            config,
        )
    )
    # Send order button callback
    send_order_button.on_click(
        lambda e: core.send_order(
            e,
            config,
            app,
            person,
        )
    )
    # Delete order button callback
    delete_order_button.on_click(
        lambda e: core.delete_order(
            e,
            config,
            app,
            person,
        )
    )

    # Callback on every "toggle" action
    @pn.depends(toggle_no_more_order_button, watch=True)
    def no_more_order_button_callback(toggle_button):
        reload_on_no_more_order(toggle_button, config)


# UTILITY FUNCTIONS
def build_order_table(df: pd.DataFrame, time: str) -> pnw.Tabulator:
    orders_table_widget = pnw.Tabulator(
        name=time,
        value=df,
        frozen_columns=[0],
        sizing_mode="stretch_width",
        layout="fit_data_stretch",
    )
    # Make the table non-editable
    orders_table_widget.editors = {c: None for c in df.columns}

    return orders_table_widget


def build_time_col_title(config: DictConfig) -> pn.pane.HTML:
    title = pn.pane.Markdown(
        config.panel.time_column_text,
        sizing_mode="stretch_width",
        style={"text-align": "center", "display": "block"},
    )

    return title


def build_time_label(
    time: str,
    diners_n: str,
    style: DictConfig,
    separator: str = " &#10072; ",
    emoji: str = random.choice(food_emoji),
    per_icon: str = " &#10006; ",
    **kwargs,
) -> pn.pane.HTML:
    time_label = pn.pane.HTML(
        f"{time}{separator}{emoji}{per_icon}{diners_n}",
        style=style,
        **kwargs,
    )

    return time_label


# MODAL WINDOW ----------------------------------------------------------------
# Error message
error_message = pn.pane.HTML(
    style={"color": "red", "font-weight": "bold"},
    sizing_mode="stretch_width",
)
error_message.visible = False
# Confirm message
confirm_message = pn.pane.HTML(
    style={"color": "green", "font-weight": "bold"},
    sizing_mode="stretch_width",
)
confirm_message.visible = False

# SIDEBAR ---------------------------------------------------------------------
# WIDGET
# File upload
file_widget = pnw.FileInput(accept=".png,.jpg,.jpeg,.xlsx")
# Stats table
# Create stats table (non-editable)
stats_widget = pnw.Tabulator(
    name="Statistics",
    hidden_columns=["index"],
    width=sidebar_width - 20,
    layout="fit_columns",
)

# BUTTONS
# Create menu button
build_menu_button = pnw.Button(
    name="Build Menu", button_type="primary", sizing_mode="stretch_width"
)
# Create download button (placeholder, defined with callbacks)
download_button = pn.widgets.FileDownload()

# COLUMNS
# Create column for uploading image/Excel with the menu
sidebar_menu_upload_col = pn.Column(
    upload_text,
    file_widget,
    build_menu_button,
    name="Menu Upload",
    width=sidebar_width,
)
# Create column for downloading Excel with orders
sidebar_download_orders_col = pn.Column(
    download_text,
    pn.widgets.FileDownload(),  # placeholder for download button (replaced in the define_sidebar_section_callbacks)
    name="Download Orders",
    width=sidebar_width,
)
# Create column for statistics
sidebar_stats_col = pn.Column(name="Stats", width=sidebar_width)
# Sidebar tabs
# The person column is defined in the app factory function because lunch
# times are configurable
sidebar_tabs = pn.Tabs(
    pn.Column(
        name="User"
    ),  # placeholder for Person data (replaced in the app factory function)
    sidebar_menu_upload_col,
    sidebar_download_orders_col,
    sidebar_stats_col,
    width=sidebar_width,
)


# CALLBACKS
def define_sidebar_section_callbacks(config: DictConfig, app: pn.Template):
    # Build menu button callback
    build_menu_button.on_click(
        lambda e: core.build_menu(
            e,
            config,
            app,
        )
    )
    # Download button and callback
    download_button = pn.widgets.FileDownload(
        callback=lambda: core.download_dataframe(config, app),
        filename=config.panel.file_name + ".xlsx",
    )
    sidebar_download_orders_col.objects[-1] = download_button


# UTILITY FUNCTIONS
def build_stats_text(
    df_stats: pd.DataFrame, version: str, host_name: str
) -> dict:
    # Stats top text
    stats = pn.pane.HTML(
        f"""
        <h3>Statistics</h3>
        <div>
            Grumbling stomachs fed:<br>
            <span style="color:green;">Locals&nbsp;&nbsp;{df_stats['Starving Locals'].sum()}</span><br>
            <span style="color:darkorange;">Guests&nbsp;&nbsp;{df_stats['Ravenous Guests'].sum()}</span><br>
            =================<br>
            <strong>TOTAL&nbsp;&nbsp;{df_stats['Hungry People'].sum()}</strong><br>
            <br>
        </div>
        <div>
            <i>See the table for details</i>
        </div>
    """
    )
    # Other info
    other_info = pn.pane.HTML(
        f"""
        <h4>Other Info</h3>
        <div>
            <i class="fa-solid fa-tag" style="font-size: 1.15rem;"></i>&nbsp;<strong>Version:</strong> <i>{version}</i>
            <br>
            <i class="fa-solid fa-microchip" style="font-size: 1.15rem;"></i>&nbsp;<strong>Host:</strong> <i>{host_name}</i>
        </div>
        """,
        sizing_mode="stretch_width",
    )

    return {"stats": stats, "info": other_info}

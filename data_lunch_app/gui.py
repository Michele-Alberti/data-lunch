import datetime
from hydra.utils import instantiate
import logging
from omegaconf import DictConfig
import pandas as pd
import panel as pn
import panel.widgets as pnw
import param
import pathlib

# Database imports
from . import models

# Core imports
from . import core

log = logging.getLogger(__name__)


# OPTIONS AND DEFAULTS --------------------------------------------------------
# App
sidebar_width = 400


# CLASS -----------------------------------------------------------------------
class Person(param.Parameterized):
    username = param.String(default="", doc="your name")
    lunch_time = param.ObjectSelector(
        default="12:30", doc="orario", objects=["12:30"]
    )
    guest = param.Boolean(default=False, doc="guest flag")
    takeaway = param.Boolean(default=False, doc="takeaway flag")
    note = param.String(default="", doc="note")

    def __init__(self, config, **params):
        super().__init__(**params)
        self.param["lunch_time"].objects = config.panel.lunch_times_options

    def __str__(self):
        return f"PERSON:{self.name}"


# CSS FILES -------------------------------------------------------------------
css_files = []


# CUSTOM CSS ------------------------------------------------------------------
header_css = """
  @import url('https://fonts.googleapis.com/css2?family=Silkscreen:wght@700&display=swap');

  .app-header .title {
    font-family: "Silkscreen", cursive;
    font-size: 2rem;
    line-height: 2rem;
  }
"""
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
# List for panel.extension
raw_css_list = [header_css, sidenav_css, tabulator_css, button_css]

# JS FILES --------------------------------------------------------------------
# Font awesome icons
js_files = {"fa-icon": "https://kit.fontawesome.com/377fe96f85.js"}


# STATIC TEXTS ----------------------------------------------------------------
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


# QUOTES ----------------------------------------------------------------------
# Quote table
quotes_filename = pathlib.Path(__file__).parent / "quotes.xlsx"
df_quotes = pd.read_excel(quotes_filename)
# Quote of the day
seed_day = int(datetime.datetime.today().strftime("%Y%m%d"))
df_quote = df_quotes.sample(n=1, random_state=seed_day)


# USER INTERFACE CLASS ========================================================
class GraphicInterface:
    def __init__(self, config: DictConfig, app: pn.Template, person: Person):
        # HEADER SECTION ------------------------------------------------------
        # WIDGET
        # Create PNG pane with app icon
        self.header_object = instantiate(config.panel.gui.header_object)

        # MAIN SECTION --------------------------------------------------------
        # Elements required for build the main section of the web app

        # TEXTS
        # Quote of the day
        self.quote = pn.pane.Markdown(
            f"""
            _{df_quote.quote.iloc[0]}_

            **{df_quote.author.iloc[0]}**
            """
        )
        # Time column title
        self.time_col_title = pn.pane.Markdown(
            config.panel.time_column_text,
            sizing_mode="stretch_width",
            style={"text-align": "center"},
        )
        # "no more order" message
        self.no_more_order_text = pn.pane.HTML(
            """
            <div style="font-size: 1.25rem; color: crimson; background-color: whitesmoke; border-left: 0.5rem solid crimson; padding: 0.5rem">
                <i class="fa-solid fa-circle-exclamation fa-fade" style="--fa-animation-duration: 1.5s;"></i> <strong>Oh no! You missed this train...</strong><br>
                Orders are closed, better luck next time.
            </div>
            """,
            margin=5,
            sizing_mode="stretch_width",
        )
        # Takeaway alert
        self.takeaway_alert_sign = (
            f"<i {config.panel.gui.takeaway_alert_icon_options}></i>"
        )
        self.takeaway_alert_text = f"<span {config.panel.gui.takeaway_alert_text_options}>{config.panel.gui.takeaway_id}</span> "

        # WIDGETS
        # Create dataframe instance
        self.dataframe = pnw.Tabulator(name="Order")

        # BUTTONS
        # Create refresh button
        # Text is centered thanks to CSS extension via pn.extension (see above)
        self.refresh_button = pnw.Button(
            name="⟲",
            width=45,
            height=45,
            align=("end", "start"),
            css_classes=["refresh-button"],
        )
        # Create send button
        self.send_order_button = pnw.Button(
            name="✔ Send Order", button_type="primary", width=150
        )
        # Create toggle button that stop orders (used in time column)
        # Initialized to False, but checked on app creation
        self.toggle_no_more_order_button = pnw.Toggle(
            value=False,
            name="⌛ Stop Orders",
            width=150,
        )
        # Create delete order
        self.delete_order_button = pnw.Button(
            name="✖ Delete Order", button_type="danger", width=150
        )

        # ROWS
        self.main_header_row = pn.Row(
            "# Menu",
            pn.layout.HSpacer(),
            self.refresh_button,
        )

        # COLUMNS
        # Create column for lunch time labels
        self.time_col = pn.Column(width=85)
        # Create column for resulting menus
        self.res_col = pn.Column(sizing_mode="stretch_width")

        # FLEXBOXES
        self.menu_flexbox = pn.FlexBox(
            *[self.dataframe, pn.Spacer(width=5), self.time_col],
            sizing_mode="stretch_height",
        )
        self.buttons_flexbox = pn.FlexBox(
            *[
                self.send_order_button,
                self.toggle_no_more_order_button,
                self.delete_order_button,
            ]
        )

        # CALLBACKS
        # Callback on every "toggle" action
        @pn.depends(self.toggle_no_more_order_button, watch=True)
        def reload_on_no_more_order_callback(toggle_button: pnw.Toggle):
            # Update global variable
            session = models.create_session(config)
            models.set_flag(
                session=session, id="no_more_orders", value=toggle_button
            )

            # Show "no more order" text
            self.no_more_order_text.visible = toggle_button

            # Deactivate send order and delete order buttons
            self.send_order_button.disabled = toggle_button
            self.delete_order_button.disabled = toggle_button

            # Simply reload the menu when the toggle button value changes
            core.reload_menu(
                None,
                config,
                self,
            )

        # Add callback to attribute
        self.reload_on_no_more_order = reload_on_no_more_order_callback

        # Refresh button callback
        self.refresh_button.on_click(
            lambda e: core.reload_menu(
                e,
                config,
                self,
            )
        )
        # Send order button callback
        self.send_order_button.on_click(
            lambda e: core.send_order(
                e,
                config,
                app,
                person,
                self,
            )
        )
        # Delete order button callback
        self.delete_order_button.on_click(
            lambda e: core.delete_order(
                e,
                config,
                app,
                person,
                self,
            )
        )

        # MODAL WINDOW --------------------------------------------------------
        # Error message
        self.error_message = pn.pane.HTML(
            style={"color": "red", "font-weight": "bold"},
            sizing_mode="stretch_width",
        )
        self.error_message.visible = False
        # Confirm message
        self.confirm_message = pn.pane.HTML(
            style={"color": "green", "font-weight": "bold"},
            sizing_mode="stretch_width",
        )
        self.confirm_message.visible = False

        # SIDEBAR -------------------------------------------------------------
        # TEXTS
        # Foldable salad menu
        self.salad_menu = pn.pane.HTML(
            f"""
            <details>
                <summary><strong>Salad menu</strong></summary>
                {config.panel.salad_list}
            </details>
            """,
            width=sidebar_width,
        )

        # WIDGET
        # Person data
        self.person_widget = pn.Param(person.param, width=sidebar_width)
        # File upload
        self.file_widget = pnw.FileInput(accept=".png,.jpg,.jpeg,.xlsx")
        # Stats table
        # Create stats table (non-editable)
        self.stats_widget = pnw.Tabulator(
            name="Statistics",
            hidden_columns=["index"],
            width=sidebar_width - 20,
            layout="fit_columns",
        )

        # BUTTONS
        # Create menu button
        self.build_menu_button = pnw.Button(
            name="Build Menu",
            button_type="primary",
            sizing_mode="stretch_width",
        )
        # Download button and callback
        self.download_button = pn.widgets.FileDownload(
            callback=lambda: core.download_dataframe(config, app, self),
            filename=config.panel.file_name + ".xlsx",
        )

        # COLUMNS
        # Create column for person data
        self.person_column = pn.Column(
            person_text,
            self.person_widget,
            pn.Spacer(height=5),
            self.salad_menu,
            name="User",
            width=sidebar_width,
        )
        # Create column for uploading image/Excel with the menu
        self.sidebar_menu_upload_col = pn.Column(
            upload_text,
            self.file_widget,
            self.build_menu_button,
            name="Menu Upload",
            width=sidebar_width,
        )
        # Create column for downloading Excel with orders
        self.sidebar_download_orders_col = pn.Column(
            download_text,
            self.download_button,
            name="Download Orders",
            width=sidebar_width,
        )
        # Create column for statistics
        self.sidebar_stats_col = pn.Column(name="Stats", width=sidebar_width)

        # TABS
        # The person column is defined in the app factory function because lunch
        # times are configurable
        self.sidebar_tabs = pn.Tabs(
            self.person_column,
            self.sidebar_menu_upload_col,
            self.sidebar_download_orders_col,
            self.sidebar_stats_col,
            width=sidebar_width,
        )

        # CALLBACKS
        # Build menu button callback
        self.build_menu_button.on_click(
            lambda e: core.build_menu(
                e,
                config,
                app,
                self,
            )
        )

    # UTILITY FUNCTIONS
    # MAIN SECTION
    def build_order_table(
        self,
        config: DictConfig,
        df: pd.DataFrame,
        time: str,
        guests_list: list[str] = [],
    ) -> pnw.Tabulator:
        # Add guest icon to users' id
        df.columns = [
            f"{c} 💰"
            if (c in guests_list) and (c != config.panel.gui.total_column_name)
            else c
            for c in df.columns
        ]
        # Create table widget
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

    def build_time_label(
        self,
        time: str,
        diners_n: str,
        separator: str = " &#10072; ",
        emoji: str = "&#127829;",
        per_icon: str = " &#10006; ",
        is_takeaway: bool = False,
        takeaway_alert_sign: str = "TAKEAWAY",
        style: dict = {},
        **kwargs,
    ) -> pn.pane.HTML:
        # Add default style elements to dict
        style.update({"text-align": "center"})
        # If takeaway add alert sign
        if is_takeaway:
            takeaway = f"{separator}{takeaway_alert_sign}"
        else:
            takeaway = ""
        # Time label pane
        time_label = pn.pane.HTML(
            f"{time}{separator}{emoji}{per_icon}{diners_n}{takeaway}",
            style=style,
            **kwargs,
        )

        return time_label

    # SIDEBAR SECTION
    def build_stats_text(
        self, df_stats: pd.DataFrame, version: str, host_name: str
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

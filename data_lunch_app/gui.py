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
        default="12:30", doc="choose your lunch time", objects=["12:30"]
    )
    guest = param.Boolean(default=False, doc="tick if you are a guest")
    takeaway = param.Boolean(
        default=False, doc="tick to order a takeaway meal"
    )
    note = param.String(default="", doc="write your notes here")

    def __init__(self, config, **params):
        super().__init__(**params)
        self.param["lunch_time"].objects = config.panel.lunch_times_options

    def __str__(self):
        return f"PERSON:{self.name}"


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
            styles={"text-align": "center"},
        )
        # "no more order" message
        self.no_more_order_text = pn.pane.HTML(
            """
            <div class="no-more-order-flag">
                <div class="icon-container">
                    <svg class="flashing-animation" xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-alert-circle-filled" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                        <path stroke="none" d="M0 0h24v24H0z" fill="none"></path>
                        <path d="M12 2c5.523 0 10 4.477 10 10a10 10 0 0 1 -19.995 .324l-.005 -.324l.004 -.28c.148 -5.393 4.566 -9.72 9.996 -9.72zm.01 13l-.127 .007a1 1 0 0 0 0 1.986l.117 .007l.127 -.007a1 1 0 0 0 0 -1.986l-.117 -.007zm-.01 -8a1 1 0 0 0 -.993 .883l-.007 .117v4l.007 .117a1 1 0 0 0 1.986 0l.007 -.117v-4l-.007 -.117a1 1 0 0 0 -.993 -.883z" stroke-width="0" fill="currentColor"></path>
                    </svg>
                    <span><strong>Oh no! You missed this train...</strong></span>
                </div>
                <div>
                    Orders are closed, better luck next time.
                </div>
            </div>
            """,
            margin=5,
            sizing_mode="stretch_width",
            stylesheets=[config.panel.gui.css_files.no_more_orders_path],
        )
        # Takeaway alert
        self.takeaway_alert_sign = f"<span {config.panel.gui.takeaway_alert_icon_options}>{config.panel.gui.takeaway_svg_icon}</span>"
        self.takeaway_alert_text = f"<span {config.panel.gui.takeaway_alert_text_options}>{config.panel.gui.takeaway_id}</span> "

        # WIDGETS
        # Create dataframe instance
        self.dataframe = pnw.Tabulator(
            name="Order",
            stylesheets=[config.panel.gui.css_files.custom_tabulator_path],
        )

        # BUTTONS
        # Create refresh button
        self.refresh_button = pnw.Button(
            name="",
            button_style="outline",
            button_type="light",
            width=45,
            height=45,
            icon="reload",
            icon_size="2em",
        )
        # Create send button
        self.send_order_button = pnw.Button(
            name="Send Order",
            button_type="success",
            width=150,
            icon="circle-check-filled",
            icon_size="2em",
        )
        # Create toggle button that stop orders (used in time column)
        # Initialized to False, but checked on app creation
        self.toggle_no_more_order_button = pnw.Toggle(
            name="Stop Orders",
            button_style="outline",
            button_type="warning",
            width=150,
            icon="alarm",
            icon_size="2em",
        )
        # Create delete order
        self.delete_order_button = pnw.Button(
            name="Delete Order",
            button_type="danger",
            width=150,
            icon="trash-filled",
            icon_size="2em",
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
        self.res_col = pn.Column(sizing_mode="stretch_width", min_width=430)

        # FLEXBOXES
        self.menu_flexbox = pn.FlexBox(
            *[self.dataframe, pn.Spacer(width=5), self.time_col],
            sizing_mode="stretch_height",
            min_width=465,
        )
        self.buttons_flexbox = pn.FlexBox(
            *[
                self.send_order_button,
                self.toggle_no_more_order_button,
                self.delete_order_button,
            ],
            min_width=510,
        )
        self.results_divider = pn.layout.Divider(
            sizing_mode="stretch_width", min_width=510
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
            styles={"color": "red", "font-weight": "bold"},
            sizing_mode="stretch_width",
        )
        self.error_message.visible = False
        # Confirm message
        self.confirm_message = pn.pane.HTML(
            styles={"color": "green", "font-weight": "bold"},
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
        self.file_widget = pnw.FileInput(
            accept=".png,.jpg,.jpeg,.xlsx", sizing_mode="stretch_width"
        )
        # Stats table
        # Create stats table (non-editable)
        self.stats_widget = pnw.Tabulator(
            name="Statistics",
            hidden_columns=["index"],
            width=sidebar_width - 20,
            layout="fit_columns",
            stylesheets=[
                config.panel.gui.css_files.custom_tabulator_path,
                config.panel.gui.css_files.stats_tabulator_path,
            ],
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
            sizing_mode="stretch_width",
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
            stylesheets=[config.panel.gui.css_files.custom_tabulator_path],
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
        css_classes: list = [],
        stylesheets: list = [],
        **kwargs,
    ) -> pn.pane.HTML:
        # If takeaway add alert sign
        if is_takeaway:
            takeaway = f"{separator}{takeaway_alert_sign}"
        else:
            takeaway = ""
        # Time label pane
        classes_str = " ".join(css_classes)
        time_label = pn.pane.HTML(
            f'<span class="{classes_str}">{time}{separator}{emoji}{per_icon}{diners_n}{takeaway}</span>',
            stylesheets=stylesheets,
            **kwargs,
        )

        return time_label

    # SIDEBAR SECTION
    def build_stats_text(
        self,
        df_stats: pd.DataFrame,
        version: str,
        host_name: str,
        stylesheets: list = [],
    ) -> dict:
        # Stats top text
        stats = pn.pane.HTML(
            f"""
            <h3>Statistics</h3>
            <div>
                Grumbling stomachs fed:<br>
                <span id="stats-locals">Locals&nbsp;&nbsp;{df_stats['Starving Locals'].sum()}</span><br>
                <span id="stats-guests">Guests&nbsp;&nbsp;{df_stats['Ravenous Guests'].sum()}</span><br>
                =================<br>
                <strong>TOTAL&nbsp;&nbsp;{df_stats['Hungry People'].sum()}</strong><br>
                <br>
            </div>
            <div>
                <i>See the table for details</i>
            </div>
            """,
            stylesheets=stylesheets,
        )
        # Other info
        other_info = pn.pane.HTML(
            f"""
            <h4>Other Info</h3>
            <div class="icon-container">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-tag" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"></path>
                    <circle cx="8.5" cy="8.5" r="1" fill="currentColor"></circle>
                    <path d="M4 7v3.859c0 .537 .213 1.052 .593 1.432l8.116 8.116a2.025 2.025 0 0 0 2.864 0l4.834 -4.834a2.025 2.025 0 0 0 0 -2.864l-8.117 -8.116a2.025 2.025 0 0 0 -1.431 -.593h-3.859a3 3 0 0 0 -3 3z"></path>
                </svg>
                <span>
                    <strong>Version:</strong> <i>{version}</i>
                </span>
            </div>
            <div class="icon-container">
                <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-cpu" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none"></path>
                    <path d="M5 5m0 1a1 1 0 0 1 1 -1h12a1 1 0 0 1 1 1v12a1 1 0 0 1 -1 1h-12a1 1 0 0 1 -1 -1z"></path>
                    <path d="M9 9h6v6h-6z"></path>
                    <path d="M3 10h2"></path>
                    <path d="M3 14h2"></path>
                    <path d="M10 3v2"></path>
                    <path d="M14 3v2"></path>
                    <path d="M21 10h-2"></path>
                    <path d="M21 14h-2"></path>
                    <path d="M14 21v-2"></path>
                    <path d="M10 21v-2"></path>
                </svg>
                <span>
                    <strong>Host:</strong> <i>{host_name}</i>
                </span>
            </div>
            """,
            sizing_mode="stretch_width",
            stylesheets=stylesheets,
        )

        return {"stats": stats, "info": other_info}

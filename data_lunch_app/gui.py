import datetime
from hydra.utils import instantiate
import logging
from omegaconf import DictConfig, OmegaConf
import pandas as pd
import panel as pn
import panel.widgets as pnw
import param
import pathlib

# Database imports
from . import models

# Core imports
from . import core

# Auth
from . import auth

log = logging.getLogger(__name__)


# OPTIONS AND DEFAULTS --------------------------------------------------------
# App
sidebar_width = 400
sidebar_content_width = sidebar_width - 10


# CLASS -----------------------------------------------------------------------
class Person(param.Parameterized):
    username = param.String(default="", doc="your name")
    lunch_time = param.ObjectSelector(
        default="12:30", doc="choose your lunch time", objects=["12:30"]
    )
    guest = param.ObjectSelector(
        default="Guest", doc="select guest type", objects=["Guest"]
    )
    takeaway = param.Boolean(
        default=False, doc="tick to order a takeaway meal"
    )
    note = param.String(default="", doc="write your notes here")

    def __init__(self, config, **params):
        super().__init__(**params)
        # Set lunch times from config
        self.param.lunch_time.objects = config.panel.lunch_times_options
        # Set guest type from config
        self.param.guest.objects = config.panel.guest_types
        self.param.guest.default = config.panel.guest_types[0]
        self.guest = config.panel.guest_types[0]
        # Check user (a username is already set for authenticated users)
        username = auth.get_username_from_cookie(
            cookie_secret=config.server.cookie_secret
        )
        if username != "guest":
            self.username = username

    def __str__(self):
        return f"PERSON:{self.name}"


class PasswordRenewer(param.Parameterized):
    old_password = param.String(default="")
    new_password = param.String(default="")
    repeat_new_password = param.String(default="")

    def __str__(self):
        return "PasswordRenewer"


# Backend password renewer is different from the normal password renewer
# because no control on the old password is made.
# This widget is used also for creating new users (for whom an old password do
# not exist)


class BackendPasswordRenewer(param.Parameterized):
    user = param.String(
        default="",
        doc="username for password update (use 'guest' for guest user)",
    )
    password = param.String(default="")
    repeat_password = param.String(default="")

    def __str__(self):
        return "BackendPasswordRenewer"


class BackendUserEraser(param.Parameterized):
    user = param.String(default="", doc="username to be deleted")

    def __str__(self):
        return "BackendUserEraser"


# STATIC TEXTS ----------------------------------------------------------------
# Tabs section text
person_text = """
### User Data

_Authenticated users_ do not need to fill the username.<br>
_Guest users_ shall use a valid _unique_ name and select a guest type.
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

guest_user_text = """
### Guest user
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
    def __init__(
        self,
        config: DictConfig,
        app: pn.Template,
        person: Person,
        guest_password: str = "",
    ):
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
            height=45,
            icon="circle-check-filled",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Create toggle button that stop orders (used in time column)
        # Initialized to False, but checked on app creation
        self.toggle_no_more_order_button = pnw.Toggle(
            name="Stop Orders",
            button_style="outline",
            button_type="warning",
            height=45,
            icon="alarm",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Create delete order
        self.delete_order_button = pnw.Button(
            name="Delete Order",
            button_type="danger",
            height=45,
            icon="trash-filled",
            icon_size="2em",
            sizing_mode="stretch_width",
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
            min_width=465,
        )
        self.buttons_flexbox = pn.FlexBox(
            *[
                self.send_order_button,
                self.toggle_no_more_order_button,
                self.delete_order_button,
            ],
            flex_wrap="nowrap",
            min_width=465,
            sizing_mode="stretch_width",
        )
        self.results_divider = pn.layout.Divider(
            sizing_mode="stretch_width", min_width=465
        )

        # CALLBACKS
        # Callback on every "toggle" action
        @pn.depends(self.toggle_no_more_order_button, watch=True)
        def reload_on_no_more_order_callback(toggle_button: pnw.Toggle):
            # Update global variable
            models.set_flag(
                config=config, id="no_more_orders", value=toggle_button
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
            width=sidebar_content_width,
        )

        # WIDGET
        # Person data
        self.person_widget = pn.Param(
            person.param,
            widgets={
                "guest": pn.widgets.RadioButtonGroup(
                    options=OmegaConf.to_container(
                        config.panel.guest_types, resolve=True
                    ),
                    button_type="primary",
                    button_style="outline",
                )
            },
            width=sidebar_content_width,
        )
        # File upload
        self.file_widget = pnw.FileInput(
            accept=".png,.jpg,.jpeg,.xlsx", sizing_mode="stretch_width"
        )
        # Stats table
        # Create stats table (non-editable)
        self.stats_widget = pnw.Tabulator(
            name="Statistics",
            hidden_columns=["index"],
            width=sidebar_content_width - 20,
            layout="fit_columns",
            stylesheets=[
                config.panel.gui.css_files.custom_tabulator_path,
                config.panel.gui.css_files.stats_tabulator_path,
            ],
        )
        # Password renewer
        self.password_widget = pn.Param(
            PasswordRenewer().param,
            widgets={
                "old_password": pnw.PasswordInput(
                    name="Old password", placeholder="Old Password"
                ),
                "new_password": pnw.PasswordInput(
                    name="New password", placeholder="New Password"
                ),
                "repeat_new_password": pnw.PasswordInput(
                    name="Repeat new password",
                    placeholder="Repeat New Password",
                ),
            },
            name="Change password",
            width=sidebar_content_width,
        )
        # Guest password text
        self.guest_username_widget = pnw.TextInput(
            name="Username",
            placeholder="If empty reload this page.",
            value="guest",
        )
        self.guest_password_widget = pnw.PasswordInput(
            name="Password",
            placeholder="If empty reload this page.",
            value=guest_password,
        )
        # Turn off guest user if no password is set (empty string)
        if not guest_password:
            self.guest_username_widget.value = ""
            self.guest_username_widget.disabled = True
            self.guest_username_widget.placeholder = "NOT ACTIVE"
            self.guest_password_widget.value = ""
            self.guest_password_widget.disabled = True
            self.guest_password_widget.placeholder = "NOT ACTIVE"

        # BUTTONS
        # Logout button
        self.logout_button = pnw.Button(
            name="Logout",
            button_type="danger",
            button_style="outline",
            height=45,
            icon="logout",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
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
        # Password button
        self.submit_password_button = pnw.Button(
            name="Submit",
            button_type="success",
            button_style="outline",
            height=45,
            icon="key",
            icon_size="2em",
            sizing_mode="stretch_width",
        )

        # COLUMNS
        # Create column for person data
        self.person_column = pn.Column(
            person_text,
            self.person_widget,
            pn.Spacer(height=5),
            self.logout_button,
            pn.Spacer(height=5),
            self.salad_menu,
            name="User",
            width=sidebar_content_width,
        )
        # Create column for uploading image/Excel with the menu
        self.sidebar_menu_upload_col = pn.Column(
            upload_text,
            self.file_widget,
            self.build_menu_button,
            name="Menu Upload",
            width=sidebar_content_width,
        )
        # Create column for downloading Excel with orders
        self.sidebar_download_orders_col = pn.Column(
            download_text,
            self.download_button,
            name="Download Orders",
            width=sidebar_content_width,
        )
        # Create column for statistics
        self.sidebar_stats_col = pn.Column(
            name="Stats", width=sidebar_content_width
        )

        self.sidebar_password = pn.Column(
            config.panel.gui.psw_text,
            self.password_widget,
            self.submit_password_button,
            pn.Spacer(height=5),
            pn.layout.Divider(),
            guest_user_text,
            self.guest_username_widget,
            self.guest_password_widget,
            name="Password",
            width=sidebar_content_width,
        )

        # TABS
        # The person column is defined in the app factory function because lunch
        # times are configurable
        self.sidebar_tabs = pn.Tabs(
            self.person_column,
            width=sidebar_content_width,
        )

        # Append password only for non-guest users
        if (
            auth.get_username_from_cookie(config.server.cookie_secret)
            != "guest"
        ):
            self.sidebar_tabs.append(self.sidebar_menu_upload_col)
            self.sidebar_tabs.append(self.sidebar_download_orders_col)
            self.sidebar_tabs.append(self.sidebar_stats_col)
            self.sidebar_tabs.append(self.sidebar_password)

        # CALLBACKS
        # Logout callback
        self.logout_button.on_click(lambda e: auth.force_logout())
        # Build menu button callback
        self.build_menu_button.on_click(
            lambda e: core.build_menu(
                e,
                config,
                app,
                self,
            )
        )
        # Submit password button callback
        self.submit_password_button.on_click(
            lambda e: core.submit_password(self, config)
        )

    # UTILITY FUNCTIONS
    # MAIN SECTION
    def build_order_table(
        self,
        config: DictConfig,
        df: pd.DataFrame,
        time: str,
        guests_lists: list[str] = [],
    ) -> pnw.Tabulator:
        # Add guest icon to users' id
        columns_with_guests_icons = df.columns.to_series()
        for guest_type, guests_list in guests_lists.items():
            columns_with_guests_icons[
                columns_with_guests_icons.isin(guests_list)
            ] += f" {config.panel.gui.guest_icons[guest_type]}"
        df.columns = columns_with_guests_icons.to_list()
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
                <span id="stats-locals">Locals&nbsp;&nbsp;{df_stats[df_stats["Guest"] == "NotAGuest"]['Hungry People'].sum()}</span><br>
                <span id="stats-guests">Guests&nbsp;&nbsp;{df_stats[df_stats["Guest"] != "NotAGuest"]['Hungry People'].sum()}</span><br>
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


# BACKEND INTERFACE CLASS ========================================================
class BackendInterface:
    def __init__(
        self,
        config: DictConfig,
    ):
        # MAIN SECTION --------------------------------------------------------
        # Backend main section

        # TEXTS
        # "no more order" message
        self.access_denied_text = pn.pane.HTML(
            """
            <div class="no-more-order-flag">
                <div class="icon-container">
                    <svg class="flashing-animation" xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-shield-lock-filled" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                        <path stroke="none" d="M0 0h24v24H0z" fill="none"></path>
                        <path d="M11.998 2l.118 .007l.059 .008l.061 .013l.111 .034a.993 .993 0 0 1 .217 .112l.104 .082l.255 .218a11 11 0 0 0 7.189 2.537l.342 -.01a1 1 0 0 1 1.005 .717a13 13 0 0 1 -9.208 16.25a1 1 0 0 1 -.502 0a13 13 0 0 1 -9.209 -16.25a1 1 0 0 1 1.005 -.717a11 11 0 0 0 7.531 -2.527l.263 -.225l.096 -.075a.993 .993 0 0 1 .217 -.112l.112 -.034a.97 .97 0 0 1 .119 -.021l.115 -.007zm.002 7a2 2 0 0 0 -1.995 1.85l-.005 .15l.005 .15a2 2 0 0 0 .995 1.581v1.769l.007 .117a1 1 0 0 0 1.993 -.117l.001 -1.768a2 2 0 0 0 -1.001 -3.732z" stroke-width="0" fill="currentColor"></path>
                    </svg>
                    <span><strong>Access denied!</strong></span>
                </div>
            </div>
            """,
            margin=5,
            sizing_mode="stretch_width",
            stylesheets=[config.panel.gui.css_files.no_more_orders_path],
        )

        # WIDGET
        # Password renewer
        self.password_widget = pn.Param(
            BackendPasswordRenewer().param,
            widgets={
                "password": pnw.PasswordInput(
                    name="New password", placeholder="New Password"
                ),
                "repeat_password": pnw.PasswordInput(
                    name="Repeat new password",
                    placeholder="Repeat New Password",
                ),
            },
            name="Add/Update User Credentials",
            width=sidebar_content_width,
        )
        # User eraser
        self.user_eraser = pn.Param(
            BackendUserEraser().param,
            name="Delete User",
            width=sidebar_content_width,
        )
        # User list
        self.users_tabulator = pn.widgets.Tabulator(
            value=pd.DataFrame({"users": auth.list_users(config=config)}),
            name="Users",
        )

        # BUTTONS
        # Logout button
        self.exit_button = pnw.Button(
            name="Exit",
            button_type="warning",
            height=45,
            icon="door-exit",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Password button
        self.submit_password_button = pnw.Button(
            name="Submit",
            button_type="success",
            height=45,
            icon="key",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Delete User button
        self.delete_user_button = pnw.Button(
            name="Delete",
            button_type="danger",
            height=45,
            icon="trash-x-filled",
            icon_size="2em",
            sizing_mode="stretch_width",
        )

        # COLUMN
        # Create column with user credentials controls
        self.add_update_user_column = pn.Column(
            config.panel.gui.psw_text,
            self.password_widget,
            pn.VSpacer(),
            self.submit_password_button,
            pn.Spacer(height=5),
            name="Add/Update Credentials",
            width=sidebar_width,
        )
        # Create for deleting users
        self.delete_user_column = pn.Column(
            self.user_eraser,
            pn.VSpacer(),
            self.delete_user_button,
            pn.Spacer(height=5),
            name="Delete User",
            width=sidebar_width,
        )
        # Create for deleting users
        self.list_user_column = pn.Column(
            self.users_tabulator,
            pn.VSpacer(),
            pn.Spacer(height=5),
            name="Users",
            width=sidebar_width,
        )

        # ROWS
        self.backend_controls = pn.Row(
            name="Actions",
            sizing_mode="stretch_both",
            min_height=450,
        )
        # Add controls only for authenticated users
        if (
            auth.get_username_from_cookie(config.server.cookie_secret)
            != "admin"
        ):
            self.backend_controls.append(self.access_denied_text)
            self.backend_controls.append(pn.Spacer(height=15))
        else:
            self.backend_controls.append(self.add_update_user_column)
            self.backend_controls.append(self.delete_user_column)
            self.backend_controls.append(self.list_user_column)

        # Add exit button
        self.backend_main = pn.Column(
            self.backend_controls,
            pn.Spacer(height=15),
            self.exit_button,
            width=sidebar_content_width * 3,
        )

        # CALLBACKS
        # Exit callback
        self.exit_button.on_click(lambda e: self.exit_backend())

        # Submit password button callback
        def submit_password_button_callback(self, config):
            success = core.backend_submit_password(self, config)
            if success:
                self.reload_backend(config)

        self.submit_password_button.on_click(
            lambda e: submit_password_button_callback(self, config)
        )

        # Delete user callback
        def delete_user_button_callback(self):
            deleted_data = auth.remove_user(
                self.user_eraser.object.user, config=config
            )
            if deleted_data:
                self.reload_backend(config)
                pn.state.notifications.success(
                    f"User '{self.user_eraser.object.user}' deleted",
                    duration=config.panel.notifications.duration,
                )
            else:
                pn.state.notifications.error(
                    f"User '{self.user_eraser.object.user}' does not exist",
                    duration=config.panel.notifications.duration,
                )

        self.delete_user_button.on_click(
            lambda e: delete_user_button_callback(self)
        )

    # UTILITY FUNCTIONS
    # MAIN SECTION
    def reload_backend(self, config) -> None:
        self.users_tabulator.value = pd.DataFrame(
            {"users": auth.list_users(config=config)}
        )

    def exit_backend(self) -> None:
        # Edit pathname to force logout
        pn.state.location.pathname = (
            pn.state.location.pathname.split("/")[0] + "/"
        )
        pn.state.location.reload = True

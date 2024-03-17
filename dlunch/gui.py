import datetime
from hydra.utils import instantiate
import jinja2
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
from .auth import pn_user

log = logging.getLogger(__name__)


# OPTIONS AND DEFAULTS --------------------------------------------------------
# App
header_row_height = 55
header_button_width = 50
generic_button_height = 45
sidebar_width = 400
sidebar_content_width = sidebar_width - 10
time_col_width = 90
time_col_spacer_width = 5
main_area_min_width = 580 + time_col_spacer_width + time_col_width
backend_min_height = 500


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

    def __init__(self, config, **params):
        super().__init__(**params)
        # Set lunch times from config
        self.param.lunch_time.objects = config.panel.lunch_times_options
        # Set guest type from config
        self.param.guest.objects = config.panel.guest_types
        self.param.guest.default = config.panel.guest_types[0]
        self.guest = config.panel.guest_types[0]
        # Check user (a username is already set for privileged users)
        username = pn_user(config)
        if not auth.is_guest(
            user=username, config=config, allow_override=False
        ) and (username is not None):
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
    new_password = param.String(default="")
    repeat_new_password = param.String(default="")
    admin = param.Boolean(default=False, doc="add admin privileges")
    guest = param.Boolean(
        default=False,
        doc="guest account (don't add user to privileged users' table)",
    )

    def __str__(self):
        return "BackendPasswordRenewer"


class BackendAddPrivilegedUser(param.Parameterized):
    user = param.String(default="", doc="user to add")
    admin = param.Boolean(default=False, doc="add admin privileges")

    def __str__(self):
        return "BackendAddUser"


class BackendUserEraser(param.Parameterized):
    user = param.String(default="", doc="user to be deleted")

    def __str__(self):
        return "BackendUserEraser"


# STATIC TEXTS ----------------------------------------------------------------
# Tabs section text
person_text = """
### User Data

_Privileged users_ do not need to fill the username.<br>
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

        # BUTTONS
        # Backend button
        self.backend_button = pnw.Button(
            name="",
            button_type="primary",
            button_style="solid",
            width=header_button_width,
            height=generic_button_height,
            icon="adjustments",
            icon_size="2em",
        )
        # Guest override toggle button (if pressed the user act as a guest)
        self.toggle_guest_override_button = pnw.Toggle(
            button_type="primary",
            button_style="solid",
            width=header_button_width,
            height=generic_button_height,
            icon="user-bolt",
            icon_size="2em",
            stylesheets=[config.panel.gui.css_files.guest_override_path],
        )
        # Logout button
        self.logout_button = pnw.Button(
            name="",
            button_type="primary",
            button_style="solid",
            width=header_button_width,
            height=generic_button_height,
            icon="door-exit",
            icon_size="2em",
        )

        # ROW
        # Create column for person data (add logout button only if auth is active)
        self.header_row = pn.Row(
            height=header_row_height,
            sizing_mode="stretch_width",
        )
        # Append a graphic element to the left side of header
        if config.panel.gui.header_object:
            self.header_row.append(self.header_object)
        # Append a controls to the right side of header
        if auth.is_auth_active(config=config):
            self.header_row.append(pn.HSpacer())
            # Backend only for admin
            if auth.is_admin(user=pn_user(config), config=config):
                self.header_row.append(self.backend_button)
            # Guest override only for non guests
            if not auth.is_guest(
                user=pn_user(config), config=config, allow_override=False
            ):
                self.header_row.append(self.toggle_guest_override_button)
            self.header_row.append(self.logout_button)
            self.header_row.append(
                pn.pane.HTML(
                    styles=dict(background="white"), width=2, height=45
                )
            )

        # CALLBACKS
        # Backend callback
        self.backend_button.on_click(lambda e: auth.open_backend())

        # Guest override callback
        @pn.depends(self.toggle_guest_override_button, watch=True)
        def reload_on_guest_override_callback(
            toggle: pnw.ToggleIcon, reload: bool = True
        ):
            # Update global variable that control guest override
            # Only non guest can store this value in 'flags' table (guest users
            # are always guests, there is no use in sotring a flag for them)
            if not auth.is_guest(
                user=pn_user(config), config=config, allow_override=False
            ):
                models.set_flag(
                    config=config,
                    id=f"{pn_user(config)}_guest_override",
                    value=toggle,
                )
            # Show banner if override is active
            self.guest_override_alert.visible = toggle
            # Simply reload the menu when the toggle button value changes
            if reload:
                core.reload_menu(
                    None,
                    config,
                    self,
                )

        # Add callback to attribute
        self.reload_on_guest_override = reload_on_guest_override_callback

        # Logout callback
        self.logout_button.on_click(lambda e: auth.force_logout())

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
        self.no_more_order_alert = pn.pane.HTML(
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
        # Alert for guest override
        self.guest_override_alert = pn.pane.HTML(
            """
            <div class="guest-override-flag">
                <div class="icon-container">
                    <svg class="flashing-animation" xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-radioactive-filled" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                        <path d="M21 11a1 1 0 0 1 1 1a10 10 0 0 1 -5 8.656a1 1 0 0 1 -1.302 -.268l-.064 -.098l-3 -5.19a.995 .995 0 0 1 -.133 -.542l.01 -.11l.023 -.106l.034 -.106l.046 -.1l.056 -.094l.067 -.089a.994 .994 0 0 1 .165 -.155l.098 -.064a2 2 0 0 0 .993 -1.57l.007 -.163a1 1 0 0 1 .883 -.994l.117 -.007h6z" stroke-width="0" fill="currentColor" />
                        <path d="M7 3.344a10 10 0 0 1 10 0a1 1 0 0 1 .418 1.262l-.052 .104l-3 5.19l-.064 .098a.994 .994 0 0 1 -.155 .165l-.089 .067a1 1 0 0 1 -.195 .102l-.105 .034l-.107 .022a1.003 1.003 0 0 1 -.547 -.07l-.104 -.052a2 2 0 0 0 -1.842 -.082l-.158 .082a1 1 0 0 1 -1.302 -.268l-.064 -.098l-3 -5.19a1 1 0 0 1 .366 -1.366z" stroke-width="0" fill="currentColor" />
                        <path d="M9 11a1 1 0 0 1 .993 .884l.007 .117a2 2 0 0 0 .861 1.645l.237 .152a.994 .994 0 0 1 .165 .155l.067 .089l.056 .095l.045 .099c.014 .036 .026 .07 .035 .106l.022 .107l.011 .11a.994 .994 0 0 1 -.08 .437l-.053 .104l-3 5.19a1 1 0 0 1 -1.366 .366a10 10 0 0 1 -5 -8.656a1 1 0 0 1 .883 -.993l.117 -.007h6z" stroke-width="0" fill="currentColor" />
                    </svg>
                    <span><strong>Watch out! You are a guest now...</strong></span>
                </div>
                <div>
                    Guest override is active.
                </div>
            </div>
            """,
            margin=5,
            sizing_mode="stretch_width",
            stylesheets=[config.panel.gui.css_files.guest_override_path],
        )
        # Takeaway alert
        self.takeaway_alert_sign = f"<span {config.panel.gui.takeaway_alert_icon_options}>{config.panel.gui.takeaway_svg_icon}</span>"
        self.takeaway_alert_text = f"<span {config.panel.gui.takeaway_alert_text_options}>{config.panel.gui.takeaway_id}</span> "
        # No menu image attribution
        self.no_menu_image_attribution = pn.pane.HTML(
            """
            <i>
                Image by
                <a
                    href="https://www.freepik.com/free-vector/tiny-cooks-making-spaghetti-dinner-isolated-flat-illustration_11235909.htm"
                    referrerpolicy="no-referrer"
                    rel="external"
                    target="_blank"
                >
                    pch.vector
                </a>
                on Freepik
            </i>
            """,
            align="end",
            styles={
                "color": "darkgray",
                "font-size": "10px",
                "font-weight": "light",
            },
        )

        # WIDGETS
        # JPG shown when no menu is available
        self.no_menu_image = pn.pane.JPG(
            config.panel.gui.no_menu_image_path, alt_text="no menu"
        )
        # Create dataframe instance
        self.dataframe = pnw.Tabulator(
            name="Order",
            widths={config.panel.gui.note_column_name: 180},
            selectable=False,
            stylesheets=[config.panel.gui.css_files.custom_tabulator_path],
        )

        # BUTTONS
        # Create refresh button
        self.refresh_button = pnw.Button(
            name="",
            button_style="outline",
            button_type="light",
            width=45,
            height=generic_button_height,
            icon="reload",
            icon_size="2em",
        )
        # Create send button
        self.send_order_button = pnw.Button(
            name="Send Order",
            button_type="success",
            height=generic_button_height,
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
            height=generic_button_height,
            icon="alarm",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Create delete order
        self.delete_order_button = pnw.Button(
            name="Delete Order",
            button_type="danger",
            height=generic_button_height,
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
        # Create column shown when no menu is available
        self.no_menu_col = pn.Column(
            self.no_menu_image,
            self.no_menu_image_attribution,
            sizing_mode="stretch_width",
            min_width=main_area_min_width,
        )
        # Create column for lunch time labels
        self.time_col = pn.Column(width=time_col_width)
        # Create column for resulting menus
        self.res_col = pn.Column(
            sizing_mode="stretch_width", min_width=main_area_min_width
        )

        # FLEXBOXES
        self.menu_flexbox = pn.FlexBox(
            *[
                self.dataframe,
                pn.Spacer(width=time_col_spacer_width),
                self.time_col,
            ],
            min_width=main_area_min_width,
        )
        self.buttons_flexbox = pn.FlexBox(
            *[
                self.send_order_button,
                self.toggle_no_more_order_button,
                self.delete_order_button,
            ],
            flex_wrap="nowrap",
            min_width=main_area_min_width,
            sizing_mode="stretch_width",
        )
        self.results_divider = pn.layout.Divider(
            sizing_mode="stretch_width", min_width=main_area_min_width
        )

        # CALLBACKS
        # Callback on every "toggle" action
        @pn.depends(self.toggle_no_more_order_button, watch=True)
        def reload_on_no_more_order_callback(
            toggle: pnw.Toggle, reload: bool = True
        ):
            # Update global variable
            models.set_flag(config=config, id="no_more_orders", value=toggle)

            # Show "no more order" text
            self.no_more_order_alert.visible = toggle

            # Deactivate send order and delete order buttons
            self.send_order_button.disabled = toggle
            self.delete_order_button.disabled = toggle

            # Simply reload the menu when the toggle button value changes
            if reload:
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
        # Foldable additional item details dropdown menu
        jinja_template = jinja2.Environment(
            loader=jinja2.BaseLoader
        ).from_string(config.panel.gui.additional_item_details_template)
        self.additional_items_details = pn.pane.HTML(
            jinja_template.render(
                items=config.panel.additional_items_to_concat
            ),
            width=sidebar_content_width,
        )

        # WIDGET
        # Person data
        self.person_widget = pn.Param(
            person.param,
            widgets={
                "guest": pnw.RadioButtonGroup(
                    options=OmegaConf.to_container(
                        config.panel.guest_types, resolve=True
                    ),
                    button_type="primary",
                    button_style="outline",
                ),
                "username": pnw.TextInput(
                    value=person.username,
                    value_input=person.username,
                    description=person.param.username.doc,
                ),
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
        # Create menu button
        self.build_menu_button = pnw.Button(
            name="Build Menu",
            button_type="primary",
            sizing_mode="stretch_width",
            icon="tools-kitchen-2",
            icon_size="2em",
        )
        # Download button and callback
        self.download_button = pn.widgets.FileDownload(
            callback=lambda: core.download_dataframe(config, app, self),
            filename=config.panel.file_name + ".xlsx",
            sizing_mode="stretch_width",
            icon="download",
            icon_size="2em",
        )
        # Password button
        self.submit_password_button = pnw.Button(
            name="Submit",
            button_type="success",
            button_style="outline",
            height=generic_button_height,
            icon="key",
            icon_size="2em",
            sizing_mode="stretch_width",
        )

        # COLUMNS
        # Create column for person data
        self.sidebar_person_column = pn.Column(
            person_text,
            self.person_widget,
            pn.Spacer(height=5),
            self.additional_items_details,
            name="User",
            width=sidebar_content_width,
        )
        # Leave an empty widget for the 'other info' section
        self.sidebar_person_column.append(
            pn.pane.HTML(),
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
        # The person widget is defined in the app factory function because
        # lunch times are configurable
        self.sidebar_tabs = pn.Tabs(
            width=sidebar_content_width,
        )
        # Reload tabs according to auth.is_guest results and guest_override
        # flag (no need to oad, tabs are already empty)
        self.load_sidebar_tabs(config=config, clear_before_loading=False)

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
        # Submit password button callback
        self.submit_password_button.on_click(
            lambda e: core.submit_password(gi=self, config=config)
        )

    # UTILITY FUNCTIONS
    # MAIN SECTION
    def build_order_table(
        self,
        config: DictConfig,
        df: pd.DataFrame,
        time: str,
        guests_lists: dict = {},
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
            layout="fit_data_table",
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
    def load_sidebar_tabs(
        self, config: DictConfig, clear_before_loading: bool = True
    ):
        # Clean tabs
        if clear_before_loading:
            self.sidebar_tabs.clear()
        # Append User tab
        self.sidebar_tabs.append(self.sidebar_person_column)
        # Append upload, download and stats only for non-guest
        # Append password only for non-guest users if auth is active
        if not auth.is_guest(
            user=pn_user(config), config=config, allow_override=False
        ):
            self.sidebar_tabs.append(self.sidebar_menu_upload_col)
            self.sidebar_tabs.append(self.sidebar_download_orders_col)
            self.sidebar_tabs.append(self.sidebar_stats_col)
            if auth.is_basic_auth_active(config=config):
                self.sidebar_tabs.append(self.sidebar_password)

    def build_stats_and_info_text(
        self,
        config: DictConfig,
        df_stats: pd.DataFrame,
        user: str,
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
        # Define user group
        if auth.is_guest(user=user, config=config, allow_override=False):
            user_group = "guest"
        elif auth.is_admin(user=user, config=config):
            user_group = "admin"
        else:
            user_group = "user"
        # Other info
        other_info = pn.pane.HTML(
            f"""
            <details>
                <summary><strong>Other Info</strong></summary>
                <div class="icon-container">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-user-square" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                        <path d="M9 10a3 3 0 1 0 6 0a3 3 0 0 0 -6 0" />
                        <path d="M6 21v-1a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v1" />
                        <path d="M3 5a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-14z" />
                    </svg>
                    <span>
                        <strong>User:</strong> <i>{user}</i>
                    </span>
                </div>
                <div class="icon-container">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-users-group" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                        <path d="M10 13a2 2 0 1 0 4 0a2 2 0 0 0 -4 0" />
                        <path d="M8 21v-1a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v1" />
                        <path d="M15 5a2 2 0 1 0 4 0a2 2 0 0 0 -4 0" />
                        <path d="M17 10h2a2 2 0 0 1 2 2v1" />
                        <path d="M5 5a2 2 0 1 0 4 0a2 2 0 0 0 -4 0" />
                        <path d="M3 13v-1a2 2 0 0 1 2 -2h2" />
                    </svg>
                    <span>
                        <strong>Group:</strong> <i>{user_group}</i>
                    </span>
                </div>
                <div class="icon-container">
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-pizza" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                        <path d="M12 21.5c-3.04 0 -5.952 -.714 -8.5 -1.983l8.5 -16.517l8.5 16.517a19.09 19.09 0 0 1 -8.5 1.983z" />
                        <path d="M5.38 15.866a14.94 14.94 0 0 0 6.815 1.634a14.944 14.944 0 0 0 6.502 -1.479" />
                        <path d="M13 11.01v-.01" />
                        <path d="M11 14v-.01" />
                    </svg>
                    <span>
                        <strong>Data-Lunch:</strong> <i>v{version}</i>
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
            </details>
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
        # HEADER SECTION ------------------------------------------------------
        # WIDGET

        # BUTTONS
        self.exit_button = pnw.Button(
            name="",
            button_type="primary",
            button_style="solid",
            width=header_button_width,
            height=generic_button_height,
            icon="home-move",
            icon_size="2em",
        )

        # ROW
        # Create column for person data (add logout button only if auth is active)
        self.header_row = pn.Row(
            height=header_row_height,
            sizing_mode="stretch_width",
        )
        # Append a controls to the right side of header
        self.header_row.append(pn.HSpacer())
        self.header_row.append(self.exit_button)
        self.header_row.append(
            pn.pane.HTML(styles=dict(background="white"), width=2, height=45)
        )

        # CALLBACKS
        # Exit callback
        self.exit_button.on_click(lambda e: self.exit_backend())

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
                    <span><strong>Insufficient privileges!</strong></span>
                </div>
            </div>
            """,
            margin=5,
            sizing_mode="stretch_width",
            stylesheets=[config.panel.gui.css_files.no_more_orders_path],
        )

        # WIDGET
        # Password renewer (only basic auth)
        self.password_widget = pn.Param(
            BackendPasswordRenewer().param,
            widgets={
                "new_password": pnw.PasswordInput(
                    name="New password", placeholder="New Password"
                ),
                "repeat_new_password": pnw.PasswordInput(
                    name="Repeat new password",
                    placeholder="Repeat New Password",
                ),
            },
            name="Add/Update User Credentials",
            width=sidebar_content_width,
        )
        # Add user (only oauth)
        self.add_privileged_user_widget = pn.Param(
            BackendAddPrivilegedUser().param,
            name="Add Privileged User",
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
            value=auth.list_users_guests_and_privileges(config),
            sizing_mode="stretch_height",
        )
        # Flags content (use empty dataframe to instantiate)
        df_flags = models.Flags.read_as_df(
            config=config,
            index_col="id",
        )
        self.flags_content = pn.widgets.Tabulator(
            value=df_flags,
            sizing_mode="stretch_height",
        )

        # BUTTONS
        # Exit button
        # Password button
        self.submit_password_button = pnw.Button(
            name="Submit",
            button_type="success",
            height=generic_button_height,
            icon="key",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Delete User button
        self.add_privileged_user_button = pnw.Button(
            name="Add",
            button_type="success",
            height=generic_button_height,
            icon="user-plus",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Delete User button
        self.delete_user_button = pnw.Button(
            name="Delete",
            button_type="danger",
            height=generic_button_height,
            icon="user-minus",
            icon_size="2em",
            sizing_mode="stretch_width",
        )
        # Clear flags table button
        self.clear_flags_button = pnw.Button(
            name="Clear Guest Override Flags",
            button_type="danger",
            height=generic_button_height,
            icon="file-shredder",
            icon_size="2em",
            sizing_mode="stretch_width",
        )

        # COLUMN
        # Create column with user credentials controls (basic auth)
        self.add_update_user_column = pn.Column(
            config.panel.gui.psw_text,
            self.password_widget,
            pn.VSpacer(),
            self.submit_password_button,
            width=sidebar_width,
            sizing_mode="stretch_height",
            min_height=backend_min_height,
        )
        # Create column with user authenthication controls (oauth)
        self.add_privileged_user_column = pn.Column(
            self.add_privileged_user_widget,
            pn.VSpacer(),
            self.add_privileged_user_button,
            width=sidebar_width,
            sizing_mode="stretch_height",
            min_height=backend_min_height,
        )
        # Create column for deleting users
        self.delete_user_column = pn.Column(
            self.user_eraser,
            pn.VSpacer(),
            self.delete_user_button,
            width=sidebar_width,
            sizing_mode="stretch_height",
            min_height=backend_min_height,
        )
        # Create column with flags' list
        self.clear_flags_column = pn.Column(
            pn.pane.HTML("<b>Flags Table Content</b>"),
            self.flags_content,
            self.clear_flags_button,
            width=sidebar_width,
            sizing_mode="stretch_height",
            min_height=backend_min_height,
        )
        # Create column for users' list
        self.list_user_column = pn.Column(
            pn.pane.HTML("<b>Users and Privileges</b>"),
            self.users_tabulator,
            width=sidebar_width,
            sizing_mode="stretch_height",
            min_height=backend_min_height,
        )

        # ROWS
        self.backend_controls = pn.Row(
            name="Actions",
            sizing_mode="stretch_both",
            min_height=backend_min_height,
        )
        # Add controls only for admin users
        if not auth.is_admin(user=pn_user(config), config=config):
            self.backend_controls.append(self.access_denied_text)
            self.backend_controls.append(pn.Spacer(height=15))
        else:
            # For basic auth use a password renewer, for oauth a widget for
            # adding privileged users
            if auth.is_basic_auth_active(config=config):
                self.backend_controls.append(self.add_update_user_column)
            else:
                self.backend_controls.append(self.add_privileged_user_column)
            self.backend_controls.append(
                pn.pane.HTML(
                    styles=dict(background="lightgray"),
                    width=2,
                    sizing_mode="stretch_height",
                )
            )
            self.backend_controls.append(self.delete_user_column)
            self.backend_controls.append(
                pn.pane.HTML(
                    styles=dict(background="lightgray"),
                    width=2,
                    sizing_mode="stretch_height",
                )
            )
            self.backend_controls.append(self.clear_flags_column)
            self.backend_controls.append(
                pn.pane.HTML(
                    styles=dict(background="lightgray"),
                    width=2,
                    sizing_mode="stretch_height",
                )
            )
            self.backend_controls.append(self.list_user_column)

        # CALLBACKS
        # Submit password button callback
        def submit_password_button_callback(self, config):
            success = core.backend_submit_password(
                gi=self,
                is_admin=self.password_widget.object.admin,
                is_guest=self.password_widget.object.guest,
                config=config,
            )
            if success:
                self.reload_backend(config)

        self.submit_password_button.on_click(
            lambda e: submit_password_button_callback(self, config)
        )

        # Add privileged user callback
        def add_privileged_user_button_callback(self):
            # Get username, updated at each key press
            username_key_press = self.add_privileged_user_widget._widgets[
                "user"
            ].value_input
            # Add user
            auth.add_privileged_user(
                username_key_press,
                is_admin=self.add_privileged_user_widget.object.admin,
                config=config,
            )

            self.reload_backend(config)
            pn.state.notifications.success(
                f"User '{username_key_press}' added",
                duration=config.panel.notifications.duration,
            )

        self.add_privileged_user_button.on_click(
            lambda e: add_privileged_user_button_callback(self)
        )

        # Delete user callback
        def delete_user_button_callback(self):
            # Get username, updated at each key press
            username_key_press = self.user_eraser._widgets["user"].value_input
            # Delete user
            deleted_data = auth.remove_user(
                user=username_key_press, config=config
            )
            if (deleted_data["privileged_users_deleted"] > 0) or (
                deleted_data["credentials_deleted"] > 0
            ):
                self.reload_backend(config)
                pn.state.notifications.success(
                    f"User '{self.user_eraser.object.user}' deleted<br>auth: {deleted_data['privileged_users_deleted']}<br>cred: {deleted_data['credentials_deleted']}",
                    duration=config.panel.notifications.duration,
                )
            else:
                pn.state.notifications.error(
                    f"User '{username_key_press}' does not exist",
                    duration=config.panel.notifications.duration,
                )

        self.delete_user_button.on_click(
            lambda e: delete_user_button_callback(self)
        )

        # Clear flags callback
        def clear_flags_button_callback(self):
            # Clear flags
            num_rows_deleted = models.Flags.clear_guest_override(config=config)
            # Reload and notify user
            self.reload_backend(config)
            pn.state.notifications.success(
                f"Guest override flags cleared<br>{num_rows_deleted} rows deleted",
                duration=config.panel.notifications.duration,
            )

        self.clear_flags_button.on_click(
            lambda e: clear_flags_button_callback(self)
        )

    # UTILITY FUNCTIONS
    # MAIN SECTION
    def reload_backend(self, config) -> None:
        # Users and guests lists
        self.users_tabulator.value = auth.list_users_guests_and_privileges(
            config
        )
        # Flags table content
        df_flags = models.Flags.read_as_df(
            config=config,
            index_col="id",
        )
        self.flags_content.value = df_flags

    def exit_backend(self) -> None:
        # Edit pathname to force exit
        pn.state.location.pathname = (
            pn.state.location.pathname.split("/")[0] + "/"
        )
        pn.state.location.reload = True

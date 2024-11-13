import cryptography.fernet
import panel as pn
import pandas as pd
import param
import pathlib
import logging
import socket
import subprocess
from omegaconf import DictConfig, OmegaConf
from openpyxl.utils import get_column_interval
from openpyxl.styles import Alignment, Font
from bokeh.models.widgets.tables import CheckboxEditor
from io import BytesIO
from PIL import Image
from pytesseract import pytesseract
import random
import re
from sqlalchemy import func, select, delete, update
from sqlalchemy.sql.expression import true as sql_true
from time import sleep

# Graphic interface imports (after class definition)
from . import models
from . import gui
from . import auth
from .auth import pn_user

# APP METADATA ----------------------------------------------------------------
__version__: str = "3.4.0"
"""Data-Lunch version."""

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# FUNCTIONS -------------------------------------------------------------------


def get_host_name(config: DictConfig) -> str:
    """Return hostname.

    This function behavior changes if called from localhost, Docker container or
    production server.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        str: hostname.
    """
    try:
        ip_address = socket.gethostbyname(socket.gethostname())
        dig_res = subprocess.run(
            ["dig", "+short", "-x", ip_address], stdout=subprocess.PIPE
        ).stdout
        host_name = (
            subprocess.run(
                ["cut", "-d.", "-f1"], stdout=subprocess.PIPE, input=dig_res
            )
            .stdout.decode("utf-8")
            .strip()
        )
        if host_name:
            host_name = host_name.replace(f"{config.docker_username}_", "")
        else:
            host_name = "no info"
    except Exception:
        host_name = "not available"

    return host_name


def delete_files(config: DictConfig) -> None:
    """Delete local temporary files.

    Args:
        config (DictConfig): Hydra configuration dictionary.
    """
    # Delete menu file if exist (every extension)
    files = list(
        pathlib.Path(config.db.shared_data_folder).glob(
            config.panel.file_name + "*"
        )
    )
    log.info(f"delete files {', '.join([f.name for f in files])}")
    for file in files:
        file.unlink(missing_ok=True)


def clean_tables(config: DictConfig) -> None:
    """Clean tables that should be reset when a new menu is uploaded.

    Args:
        config (DictConfig): Hydra configuration dictionary.
    """
    # Clean tables
    # Clean orders
    models.Orders.clear(config=config)
    # Clean menu
    models.Menu.clear(config=config)
    # Clean users
    models.Users.clear(config=config)
    # Clean flags
    models.Flags.clear_guest_override(config=config)
    # Reset flags
    models.set_flag(config=config, id="no_more_orders", value=False)
    log.info("reset values in table 'flags'")
    # Clean cache
    pn.state.clear_caches()
    log.info("cache cleaned")


def set_guest_user_password(config: DictConfig) -> str:
    """If guest user is active return a password, otherwise return an empty string.

    This function always returns an empty string if basic authentication is not active.

    Guest user and basic authentication are handled through configuration files.

    If the flag `reset_guest_user_password` is set to `True` the password is created
    and uploaded to database. Otherwise the existing password is queried from database
    `credentials` table.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        str: guest user password or empty string if basic authentication is not active.
    """
    # Check if basic auth is active
    if auth.is_basic_auth_active(config=config):
        # If active basic_auth.guest_user is true if guest user is active
        is_guest_user_active = config.basic_auth.guest_user
        log.debug("guest user flag is {is_guest_user_active}")
    else:
        # Otherwise the guest user feature is not applicable
        is_guest_user_active = False
        log.debug("guest user not applicable")

    # Set the guest password variable
    if is_guest_user_active:
        # If flag for resetting the password does not exist use the default
        # value
        if (
            models.get_flag(config=config, id="reset_guest_user_password")
            is None
        ):
            models.set_flag(
                config=config,
                id="reset_guest_user_password",
                value=config.basic_auth.default_reset_guest_user_password_flag,
            )
        # Generate a random password only if requested (check on flag)
        # otherwise load from pickle
        if models.get_flag(config=config, id="reset_guest_user_password"):
            # Turn off reset user password (in order to reset it only once)
            # This statement also acquire a lock on database (so it is
            # called first)
            models.set_flag(
                config=config,
                id="reset_guest_user_password",
                value=False,
            )
            # Create password
            guest_password = auth.generate_password(
                special_chars=config.basic_auth.psw_special_chars,
                length=config.basic_auth.generated_psw_length,
            )
            # Add hashed password to database
            auth.add_user_hashed_password(
                "guest", guest_password, config=config
            )
        else:
            # Load from database
            session = models.create_session(config)
            with session:
                try:
                    guest_password = session.get(
                        models.Credentials, "guest"
                    ).password_encrypted.decrypt()
                except cryptography.fernet.InvalidToken:
                    # Notify exception and suggest to reset guest user password
                    guest_password = ""
                    log.warning(
                        "Unable to decrypt 'guest' user password because an invalid token has been detected: reset password from backend"
                    )
                    pn.state.notifications.warning(
                        "Unable to decrypt 'guest' user password<br>Invalid token detected: reset password from backend",
                        duration=config.panel.notifications.duration,
                    )
    else:
        guest_password = ""

    return guest_password


def build_menu(
    event: param.parameterized.Event,
    config: DictConfig,
    app: pn.Template,
    gi: gui.GraphicInterface,
) -> None:
    """Read menu from file (Excel or image) and upload menu items to database `menu` table.

    Args:
        event (param.parameterized.Event): Panel button event.
        config (DictConfig): Hydra configuration dictionary.
        app (pn.Template): Panel app template (used to open modal windows in case of database errors).
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).
    """
    # Hide messages
    gi.error_message.visible = False

    # Build image path
    menu_filename = str(
        pathlib.Path(config.db.shared_data_folder) / config.panel.file_name
    )

    # Delete menu file if exist (every extension)
    delete_files(config)

    # Load file from widget
    if gi.file_widget.value is not None:
        # Find file extension
        file_ext = pathlib.PurePath(gi.file_widget.filename).suffix

        # Save file locally
        local_menu_filename = menu_filename + file_ext
        gi.file_widget.save(local_menu_filename)

        # Clean tables
        clean_tables(config)

        # File can be either an excel file or an image
        if file_ext == ".png" or file_ext == ".jpg" or file_ext == ".jpeg":
            # Transform image into a pandas DataFrame
            # Open image with PIL
            img = Image.open(local_menu_filename)
            # Extract text from image
            text = pytesseract.image_to_string(img, lang="ita")
            # Process rows (rows that are completely uppercase are section titles)
            rows = [
                row for row in text.split("\n") if row and not row.isupper()
            ]
            df = pd.DataFrame({"item": rows})
            # Concat additional items
            df = pd.concat(
                [
                    df,
                    pd.DataFrame(
                        {
                            "item": [
                                item["name"]
                                for item in config.panel.additional_items_to_concat
                            ]
                        }
                    ),
                ],
                axis="index",
            )

        elif file_ext == ".xlsx":
            log.info("excel file uploaded")
            df = pd.read_excel(
                local_menu_filename, names=["item"], header=None
            )
            # Concat additional items
            df = pd.concat(
                [
                    df,
                    pd.DataFrame(
                        {
                            "item": [
                                item["name"]
                                for item in config.panel.additional_items_to_concat
                            ]
                        }
                    ),
                ],
                axis="index",
                ignore_index=True,
            )
        else:
            df = pd.DataFrame()
            pn.state.notifications.error(
                "Wrong file type", duration=config.panel.notifications.duration
            )
            log.warning("wrong file type")
            return

        # Upload to database menu table
        engine = models.create_engine(config)
        try:
            df.drop_duplicates(subset="item").to_sql(
                models.Menu.__tablename__,
                engine,
                schema=config.db.get("schema", models.SCHEMA),
                index=False,
                if_exists="append",
            )
            # Update dataframe widget
            reload_menu(
                None,
                config,
                gi,
            )

            pn.state.notifications.success(
                "Menu uploaded", duration=config.panel.notifications.duration
            )
            log.info("menu uploaded")
        except Exception as e:
            # Any exception here is a database fault
            pn.state.notifications.error(
                "Database error", duration=config.panel.notifications.duration
            )
            gi.error_message.object = (
                f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
            )
            gi.error_message.visible = True
            log.warning("database error")
            # Open modal window
            app.open_modal()

    else:
        pn.state.notifications.warning(
            "No file selected", duration=config.panel.notifications.duration
        )
        log.warning("no file selected")


def reload_menu(
    event: param.parameterized.Event,
    config: DictConfig,
    gi: gui.GraphicInterface,
) -> None:
    """Main core function that sync Panel widget with database tables.

    Stop orders and guest override checks are carried out by this function.
    Also the banner image is shown based on a check run by this function.

    `menu`, `orders` and `users` tables are used to build a list of orders for each lunch time.
    Takeaway orders are evaluated separately.

    At the end stats about lunches are calculated and loaded to database. Finally
    statistics (values and table) shown inside the app are updated accordingly.

    Args:
        event (param.parameterized.Event): Panel button event.
        config (DictConfig): Hydra configuration dictionary.
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).
    """
    # Create session
    session = models.create_session(config)

    with session:
        # Check if someone changed the "no_more_order" toggle
        if gi.toggle_no_more_order_button.value != models.get_flag(
            config=config, id="no_more_orders"
        ):
            # The following statement will trigger the toggle callback
            # which will call reload_menu once again
            # This is the reason why this if contains a return (without the return
            # the content will be reloaded twice)
            gi.toggle_no_more_order_button.value = models.get_flag(
                config=config, id="no_more_orders"
            )

            return

        # Check guest override button status (if not in table use False)
        gi.toggle_guest_override_button.value = models.get_flag(
            config=config,
            id=f"{pn_user(config)}_guest_override",
            value_if_missing=False,
        )

        # Set no more orders toggle button and the change order time button
        # visibility and activation
        if auth.is_guest(
            user=pn_user(config), config=config, allow_override=False
        ):
            # Deactivate the no_more_orders_button for guest users
            gi.toggle_no_more_order_button.disabled = True
            gi.toggle_no_more_order_button.visible = False
            # Deactivate the change_order_time_button for guest users
            gi.change_order_time_takeaway_button.disabled = True
            gi.change_order_time_takeaway_button.visible = False
        else:
            # Activate the no_more_orders_button for privileged users
            gi.toggle_no_more_order_button.disabled = False
            gi.toggle_no_more_order_button.visible = True
            # Show the change_order_time_button for privileged users
            # It is disabled by the no more order button if necessary
            gi.change_order_time_takeaway_button.visible = True

        # Guest graphic configuration
        if auth.is_guest(user=pn_user(config), config=config):
            # If guest show guest type selection group
            gi.person_widget.widgets["guest"].disabled = False
            gi.person_widget.widgets["guest"].visible = True
        else:
            # If user is privileged hide guest type selection group
            gi.person_widget.widgets["guest"].disabled = True
            gi.person_widget.widgets["guest"].visible = False

        # Reload menu
        engine = models.create_engine(config)
        df = models.Menu.read_as_df(
            config=config,
            index_col="id",
        )
        # Add order (for selecting items) and note columns
        df["order"] = False
        df[config.panel.gui.note_column_name] = ""
        gi.dataframe.value = df
        gi.dataframe.formatters = {"order": {"type": "tickCross"}}
        gi.dataframe.editors = {
            "id": None,
            "item": None,
            "order": CheckboxEditor(),
            config.panel.gui.note_column_name: "input",
        }
        gi.dataframe.header_align = OmegaConf.to_container(
            config.panel.gui.menu_column_align, resolve=True
        )
        gi.dataframe.text_align = OmegaConf.to_container(
            config.panel.gui.menu_column_align, resolve=True
        )

        if gi.toggle_no_more_order_button.value:
            gi.dataframe.hidden_columns = ["id", "order"]
            gi.dataframe.disabled = True
        else:
            gi.dataframe.hidden_columns = ["id"]
            gi.dataframe.disabled = False

        # If menu is empty show banner image, otherwise show menu
        if df.empty:
            gi.no_menu_col.visible = True
            gi.main_header_row.visible = False
            gi.quote.visible = False
            gi.menu_flexbox.visible = False
            gi.buttons_flexbox.visible = False
            gi.results_divider.visible = False
            gi.res_col.visible = False
        else:
            gi.no_menu_col.visible = False
            gi.main_header_row.visible = True
            gi.quote.visible = True
            gi.menu_flexbox.visible = True
            gi.buttons_flexbox.visible = True
            gi.results_divider.visible = True
            gi.res_col.visible = True

        log.debug("menu reloaded")

        # Load results
        df_dict = df_list_by_lunch_time(config)
        # Clean columns and load text and dataframes
        gi.res_col.clear()
        gi.time_col.clear()
        if df_dict:
            # Titles
            gi.res_col.append(config.panel.result_column_text)
            gi.time_col.append(gi.time_col_title)
            # Build guests list (one per each guest types)
            guests_lists = {}
            for guest_type in config.panel.guest_types:
                guests_lists[guest_type] = [
                    user.id
                    for user in session.scalars(
                        select(models.Users).where(
                            models.Users.guest == guest_type
                        )
                    ).all()
                ]
            # Loop through lunch times
            for time, df in df_dict.items():
                # Find the number of grumbling stomachs
                grumbling_stomachs = len(
                    [
                        c
                        for c in df.columns
                        if c
                        not in (
                            config.panel.gui.total_column_name,
                            config.panel.gui.note_column_name,
                        )
                    ]
                )
                # Set different graphics for takeaway lunches
                if config.panel.gui.takeaway_id in time:
                    res_col_label_kwargs = {
                        "time": time.replace(config.panel.gui.takeaway_id, ""),
                        "diners_n": grumbling_stomachs,
                        "emoji": config.panel.gui.takeaway_emoji,
                        "is_takeaway": True,
                        "takeaway_alert_sign": f"&nbsp{gi.takeaway_alert_sign}&nbsp{gi.takeaway_alert_text}",
                        "css_classes": OmegaConf.to_container(
                            config.panel.gui.takeaway_class_res_col,
                            resolve=True,
                        ),
                        "stylesheets": [
                            config.panel.gui.css_files.labels_path
                        ],
                    }
                    time_col_label_kwargs = {
                        "time": time.replace(config.panel.gui.takeaway_id, ""),
                        "diners_n": str(grumbling_stomachs) + "&nbsp",
                        "separator": "<br>",
                        "emoji": config.panel.gui.takeaway_emoji,
                        "align": ("center", "center"),
                        "sizing_mode": "stretch_width",
                        "is_takeaway": True,
                        "takeaway_alert_sign": gi.takeaway_alert_sign,
                        "css_classes": OmegaConf.to_container(
                            config.panel.gui.takeaway_class_time_col,
                            resolve=True,
                        ),
                        "stylesheets": [
                            config.panel.gui.css_files.labels_path
                        ],
                    }
                else:
                    res_col_label_kwargs = {
                        "time": time,
                        "diners_n": grumbling_stomachs,
                        "emoji": random.choice(config.panel.gui.food_emoji),
                        "css_classes": OmegaConf.to_container(
                            config.panel.gui.time_class_res_col, resolve=True
                        ),
                        "stylesheets": [
                            config.panel.gui.css_files.labels_path
                        ],
                    }
                    time_col_label_kwargs = {
                        "time": time,
                        "diners_n": str(grumbling_stomachs) + "&nbsp",
                        "separator": "<br>",
                        "emoji": config.panel.gui.restaurant_emoji,
                        "per_icon": "&#10006; ",
                        "align": ("center", "center"),
                        "sizing_mode": "stretch_width",
                        "css_classes": OmegaConf.to_container(
                            config.panel.gui.time_class_time_col, resolve=True
                        ),
                        "stylesheets": [
                            config.panel.gui.css_files.labels_path
                        ],
                    }
                # Add text to result column
                gi.res_col.append(pn.Spacer(height=15))
                gi.res_col.append(gi.build_time_label(**res_col_label_kwargs))
                # Add non editable table to result column
                gi.res_col.append(pn.Spacer(height=5))
                gi.res_col.append(
                    gi.build_order_table(
                        config, df=df, time=time, guests_lists=guests_lists
                    )
                )
                # Add also a label to lunch time column
                gi.time_col.append(
                    gi.build_time_label(**time_col_label_kwargs)
                )

        log.debug("results reloaded")

        # Clean stats column
        gi.sidebar_stats_col.clear()
        # Update stats
        # Find how many people eat today (total number) and add value to database
        # stats table (when adding a stats if guest is not specified None is used
        # as default)
        today_locals_count = session.scalar(
            select(func.count(models.Users.id)).where(
                models.Users.guest == "NotAGuest"
            )
        )
        new_stat = models.Stats(hungry_people=today_locals_count)
        # Use an upsert for postgresql, a simple session add otherwise
        models.session_add_with_upsert(
            session=session, constraint="stats_pkey", new_record=new_stat
        )
        # For each guest type find how many guests eat today
        for guest_type in config.panel.guest_types:
            today_guests_count = session.scalar(
                select(func.count(models.Users.id)).where(
                    models.Users.guest == guest_type
                )
            )
            new_stat = models.Stats(
                guest=guest_type, hungry_people=today_guests_count
            )
            # Use an upsert for postgresql, a simple session add otherwise
            models.session_add_with_upsert(
                session=session, constraint="stats_pkey", new_record=new_stat
            )

        # Commit stats
        session.commit()

        # Group stats by month and return how many people had lunch
        df_stats = pd.read_sql_query(
            config.db.stats_query.format(
                schema=config.db.get("schema", models.SCHEMA)
            ),
            engine,
        )
        # Stats top text
        stats_and_info_text = gi.build_stats_and_info_text(
            config=config,
            df_stats=df_stats,
            user=pn_user(config),
            version=__version__,
            host_name=get_host_name(config),
            stylesheets=[config.panel.gui.css_files.stats_info_path],
        )
        # Remove NotAGuest (non-guest users)
        df_stats.Guest = df_stats.Guest.replace(
            "NotAGuest", config.panel.stats_locals_column_name
        )
        # Pivot table on guest type
        df_stats = df_stats.pivot(
            columns="Guest",
            index=config.panel.stats_id_cols,
            values="Hungry People",
        ).reset_index()
        df_stats[config.panel.gui.total_column_name.title()] = df_stats.sum(
            axis="columns", numeric_only=True
        )
        # Add value and non-editable option to stats table
        gi.stats_widget.editors = {c: None for c in df_stats.columns}
        gi.stats_widget.value = df_stats
        gi.sidebar_stats_col.append(stats_and_info_text["stats"])
        gi.sidebar_stats_col.append(gi.stats_widget)
        # Add info below person widget (an empty placeholder was left as last
        # element)
        gi.sidebar_person_column.objects[-1] = stats_and_info_text["info"]
        log.debug("stats and info updated")


def send_order(
    event: param.parameterized.Event,
    config: DictConfig,
    app: pn.Template,
    person: gui.Person,
    gi: gui.GraphicInterface,
) -> None:
    """Upload orders and user to database tables.

    The user target of the order is uploaded to `users` table, while the order
    is uploaded to `orders` table.

    Consistency checks about the user and the order are carried out here (existing user, only one order, etc.).
    The status of the `stop_orders` flag is checked to avoid that an order is uploaded when it shouldn't.

    Orders for guest users are marked as such before uploading them.

    Args:
        event (param.parameterized.Event): Panel button event.
        config (DictConfig): Hydra configuration dictionary.
        app (pn.Template): Panel app template (used to open modal windows in case of database errors).
        person (gui.Person): class that collect order data for the user that is the target of the order.
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).
    """
    # Get username updated at each key press
    username_key_press = gi.person_widget._widgets["username"].value_input

    # Hide messages
    gi.error_message.visible = False

    # Create session
    session = models.create_session(config)

    with session:
        # Check if the "no more order" toggle button is pressed
        if models.get_flag(config=config, id="no_more_orders"):
            pn.state.notifications.error(
                "It is not possible to place new orders",
                duration=config.panel.notifications.duration,
            )

            # Reload the menu
            reload_menu(
                None,
                config,
                gi,
            )

            return

        # If auth is active, check if a guests is using a name reserved to a
        # privileged user
        if (
            auth.is_guest(user=pn_user(config), config=config)
            and (username_key_press in auth.list_users(config=config))
            and (auth.is_auth_active(config=config))
        ):
            pn.state.notifications.error(
                f"{username_key_press} is a reserved name<br>Please choose a different one",
                duration=config.panel.notifications.duration,
            )

            # Reload the menu
            reload_menu(
                None,
                config,
                gi,
            )

            return

        # Check if a privileged user is ordering for an invalid name
        if (
            not auth.is_guest(user=pn_user(config), config=config)
            and (
                username_key_press
                not in (
                    name
                    for name in auth.list_users(config=config)
                    if name != "guest"
                )
            )
            and (auth.is_auth_active(config=config))
        ):
            pn.state.notifications.error(
                f"{username_key_press} is not a valid name<br>for a privileged user<br>Please choose a different one",
                duration=config.panel.notifications.duration,
            )

            # Reload the menu
            reload_menu(
                None,
                config,
                gi,
            )

            return

        # Write order into database table
        df = gi.dataframe.value.copy()
        df_order = df[df.order]
        # If username is missing or the order is empty return an error message
        if username_key_press and not df_order.empty:
            # Check if the user already placed an order
            if session.get(models.Users, username_key_press):
                pn.state.notifications.warning(
                    f"Cannot overwrite an order<br>Delete {username_key_press}'s order first and retry",
                    duration=config.panel.notifications.duration,
                )
                log.warning(f"an order already exist for {username_key_press}")
            else:
                # Place order
                try:
                    # Add User
                    # Do not pass guest for privileged users (default to NotAGuest)
                    if auth.is_guest(user=pn_user(config), config=config):
                        new_user = models.Users(
                            id=username_key_press,
                            guest=person.guest,
                            lunch_time=person.lunch_time,
                            takeaway=person.takeaway,
                        )
                    else:
                        new_user = models.Users(
                            id=username_key_press,
                            lunch_time=person.lunch_time,
                            takeaway=person.takeaway,
                        )
                    session.add(new_user)
                    session.commit()
                    # Add orders as long table (one row for each item selected by a user)
                    for row in df_order.itertuples(name="OrderTuple"):
                        # Order
                        new_order = models.Orders(
                            user=username_key_press,
                            menu_item_id=row.Index,
                            note=getattr(
                                row, config.panel.gui.note_column_name
                            ).lower(),
                        )
                        session.add(new_order)
                        session.commit()

                    # Update dataframe widget
                    reload_menu(
                        None,
                        config,
                        gi,
                    )

                    pn.state.notifications.success(
                        "Order sent",
                        duration=config.panel.notifications.duration,
                    )
                    log.info(f"{username_key_press}'s order saved")
                except Exception as e:
                    # Any exception here is a database fault
                    pn.state.notifications.error(
                        "Database error",
                        duration=config.panel.notifications.duration,
                    )
                    gi.error_message.object = (
                        f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
                    )
                    gi.error_message.visible = True
                    log.error("database error")
                    # Open modal window
                    app.open_modal()
        else:
            if not username_key_press:
                pn.state.notifications.warning(
                    "Please insert user name",
                    duration=config.panel.notifications.duration,
                )
                log.warning("missing username")
            else:
                pn.state.notifications.warning(
                    "Please make a selection",
                    duration=config.panel.notifications.duration,
                )
                log.warning("no selection made")


def delete_order(
    event: param.parameterized.Event,
    config: DictConfig,
    app: pn.Template,
    gi: gui.GraphicInterface,
) -> None:
    """Delete an existing order.

    Consistency checks about the user and the order are carried out here (existing user, only one order, etc.).
    The status of the `stop_orders` flag is checked to avoid that an order is uploaded when it shouldn't.

    In addition privileges are taken into account (guest users cannot delete orders that targets a privileged user).

    Args:
        event (param.parameterized.Event): Panel button event.
        config (DictConfig): Hydra configuration dictionary.
        app (pn.Template): Panel app template (used to open modal windows in case of database errors).
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).
    """
    # Get username, updated on every keypress
    username_key_press = gi.person_widget._widgets["username"].value_input

    # Hide messages
    gi.error_message.visible = False

    # Create session
    session = models.create_session(config)

    with session:
        # Check if the "no more order" toggle button is pressed
        if models.get_flag(config=config, id="no_more_orders"):
            pn.state.notifications.error(
                "It is not possible to delete orders",
                duration=config.panel.notifications.duration,
            )

            # Reload the menu
            reload_menu(
                None,
                config,
                gi,
            )

            return

        if username_key_press:
            # If auth is active, check if a guests is deleting an order of a
            # privileged user
            if (
                auth.is_guest(user=pn_user(config), config=config)
                and (username_key_press in auth.list_users(config=config))
                and (auth.is_auth_active(config=config))
            ):
                pn.state.notifications.error(
                    f"You do not have enough privileges<br>to delete<br>{username_key_press}'s order",
                    duration=config.panel.notifications.duration,
                )

                # Reload the menu
                reload_menu(
                    None,
                    config,
                    gi,
                )

                return

            # Delete user
            try:
                num_rows_deleted_users = session.execute(
                    delete(models.Users).where(
                        models.Users.id == username_key_press
                    )
                )
                # Delete also orders (hotfix for Debian)
                num_rows_deleted_orders = session.execute(
                    delete(models.Orders).where(
                        models.Orders.user == username_key_press
                    )
                )
                session.commit()
                if (num_rows_deleted_users.rowcount > 0) or (
                    num_rows_deleted_orders.rowcount > 0
                ):
                    # Update dataframe widget
                    reload_menu(
                        None,
                        config,
                        gi,
                    )

                    pn.state.notifications.success(
                        "Order canceled",
                        duration=config.panel.notifications.duration,
                    )
                    log.info(f"{username_key_press}'s order canceled")
                else:
                    pn.state.notifications.warning(
                        f'No order for user named<br>"{username_key_press}"',
                        duration=config.panel.notifications.duration,
                    )
                    log.info(f"no order for user named {username_key_press}")
            except Exception as e:
                # Any exception here is a database fault
                pn.state.notifications.error(
                    "Database error",
                    duration=config.panel.notifications.duration,
                )
                gi.error_message.object = (
                    f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
                )
                gi.error_message.visible = True
                log.error("database error")
                # Open modal window
                app.open_modal()
        else:
            pn.state.notifications.warning(
                "Please insert user name",
                duration=config.panel.notifications.duration,
            )
            log.warning("missing username")


def change_order_time_takeaway(
    event: param.parameterized.Event,
    config: DictConfig,
    person: gui.Person,
    gi: gui.GraphicInterface,
) -> None:
    """Change the time and the takeaway flag of an existing order.

    Args:
        event (param.parameterized.Event): Panel button event.
        config (DictConfig): Hydra configuration dictionary.
        person (gui.Person): class that collect order data for the user that is the target of the order.
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).
    """
    # Get username, updated on every keypress
    username_key_press = gi.person_widget._widgets["username"].value_input

    # Create session
    session = models.create_session(config)

    with session:
        # Check if the "no more order" toggle button is pressed
        if models.get_flag(config=config, id="no_more_orders"):
            pn.state.notifications.error(
                "It is not possible to update orders (time)",
                duration=config.panel.notifications.duration,
            )

            # Reload the menu
            reload_menu(
                None,
                config,
                gi,
            )

            return

        if username_key_press:
            # Build and execute the update statement
            update_statement = (
                update(models.Users)
                .where(models.Users.id == username_key_press)
                .values(lunch_time=person.lunch_time, takeaway=person.takeaway)
                .returning(models.Users)
            )

            updated_user = session.scalars(update_statement).one_or_none()

            session.commit()

            if updated_user:
                # Find updated values
                updated_time = updated_user.lunch_time
                updated_takeaway = (
                    (" " + config.panel.gui.takeaway_id)
                    if updated_user.takeaway
                    else ""
                )
                updated_items_names = [
                    order.menu_item.item for order in updated_user.orders
                ]
                # Update dataframe widget
                reload_menu(
                    None,
                    config,
                    gi,
                )

                pn.state.notifications.success(
                    f"{username_key_press}'s<br>lunch time changed to<br>{updated_time}{updated_takeaway}<br>({', '.join(updated_items_names)})",
                    duration=config.panel.notifications.duration,
                )
                log.info(f"{username_key_press}'s order updated")
            else:
                pn.state.notifications.warning(
                    f'No order for user named<br>"{username_key_press}"',
                    duration=config.panel.notifications.duration,
                )
                log.info(f"no order for user named {username_key_press}")
        else:
            pn.state.notifications.warning(
                "Please insert user name",
                duration=config.panel.notifications.duration,
            )
            log.warning("missing username")


def df_list_by_lunch_time(
    config: DictConfig,
) -> dict:
    """Build a dictionary of dataframes for each lunch-time, with takeaways included in a dedicated dataframe.

    Each datframe includes orders grouped by users, notes and a total column (with the total value
    for a specific item).

    The keys of the dataframe are `lunch-times` and `lunch-times + takeaway_id`.

    Args:
        config (DictConfig): _description_

    Returns:
        dict: dictionary with dataframes summarizing the orders for each lunch-time/takeaway-time.
    """
    # Create database engine and session
    engine = models.create_engine(config)
    # Read menu and save how menu items are sorted (first courses, second courses, etc.)
    original_order = models.Menu.read_as_df(
        config=config,
        index_col="id",
    ).item
    # Create session
    session = models.create_session(config)

    with session:
        # Build takeaway list
        takeaway_list = [
            user.id
            for user in session.scalars(
                select(models.Users).where(models.Users.takeaway == sql_true())
            ).all()
        ]
    # Read dataframe (including notes)
    df = pd.read_sql_query(
        config.db.orders_query.format(
            schema=config.db.get("schema", models.SCHEMA)
        ),
        engine,
    )

    # Build a dict of dataframes, one for each lunch time
    df_dict = {}
    for time in df.lunch_time.sort_values().unique():
        # Take only one lunch time (and remove notes so they do not alter
        # numeric counters inside the pivot table)
        temp_df = (
            df[df.lunch_time == time]
            .drop(columns=["lunch_time", "note"])
            .reset_index(drop=True)
        )
        # Users' selections
        df_users = temp_df.pivot_table(
            index="item", columns="user", aggfunc=len
        )
        # Reorder index in accordance with original menu
        df_users = df_users.reindex(original_order)
        # Split restaurant lunches from takeaway lunches
        df_users_restaurant = df_users.loc[
            :, [c for c in df_users.columns if c not in takeaway_list]
        ]
        df_users_takeaways = df_users.loc[
            :, [c for c in df_users.columns if c in takeaway_list]
        ]

        # The following function prepare the dataframe before saving it into
        # the dictionary that will be returned
        def clean_up_table(
            config: DictConfig, df_in: pd.DataFrame, df_complete: pd.DataFrame
        ):
            df = df_in.copy()
            # Group notes per menu item by concat users notes
            # Use value counts to keep track of how many time a note is repeated
            df_notes = (
                df_complete[
                    (df_complete.lunch_time == time)
                    & (df_complete.note != "")
                    & (df_complete.user.isin(df.columns))
                ]
                .drop(columns=["user", "lunch_time"])
                .value_counts()
                .reset_index(level="note")
            )
            df_notes.note = (
                df_notes["count"]
                .astype(str)
                .str.cat(df_notes.note, sep=config.panel.gui.note_sep.count)
            )
            df_notes = df_notes.drop(columns="count")
            df_notes = (
                df_notes.groupby("item")["note"]
                .apply(config.panel.gui.note_sep.element.join)
                .to_frame()
            )
            # Add columns of totals
            df[config.panel.gui.total_column_name] = df.sum(axis=1)
            # Drop unused rows if requested
            if config.panel.drop_unused_menu_items:
                df = df[df[config.panel.gui.total_column_name] > 0]
            # Add notes
            df = df.join(df_notes)
            df = df.rename(columns={"note": config.panel.gui.note_column_name})
            # Change NaNs to '-'
            df = df.fillna("-")
            # Avoid mixed types (float and notes str)
            df = df.astype(object)

            return df

        # Clean and add resulting dataframes to dict
        # RESTAURANT LUNCH
        if not df_users_restaurant.empty:
            df_users_restaurant = clean_up_table(
                config, df_users_restaurant, df
            )
            df_dict[time] = df_users_restaurant
        # TAKEAWAY
        if not df_users_takeaways.empty:
            df_users_takeaways = clean_up_table(config, df_users_takeaways, df)
            df_dict[f"{time} {config.panel.gui.takeaway_id}"] = (
                df_users_takeaways
            )

    return df_dict


def download_dataframe(
    config: DictConfig,
    gi: gui.GraphicInterface,
) -> BytesIO:
    """Build an Excel file with tables representing orders for every lunch-time/takeaway-time.

    Tables are created by the function `df_list_by_lunch_time` and exported on dedicated Excel worksheets
    (inside the same workbook).

    The result is returned as bytes stream to satisfy panel.widgets.FileDownload class requirements.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).

    Returns:
        BytesIO: download stream for the Excel file.
    """

    # Build a dict of dataframes, one for each lunch time (the key contains
    # a lunch time)
    df_dict = df_list_by_lunch_time(config)
    # Export one dataframe for each lunch time
    bytes_io = BytesIO()
    writer = pd.ExcelWriter(bytes_io)
    # If the dataframe dict is non-empty export one dataframe for each sheet
    if df_dict:
        for time, df in df_dict.items():
            log.info(f"writing sheet {time}")

            # Find users that placed an order for a given time
            users_n = len(
                [
                    c
                    for c in df.columns
                    if c
                    not in (
                        config.panel.gui.total_column_name,
                        config.panel.gui.note_column_name,
                    )
                ]
            )

            # Export dataframe to new sheet
            worksheet_name = time.replace(":", ".")
            df.to_excel(writer, sheet_name=worksheet_name, startrow=1)
            # Add title
            worksheet = writer.sheets[worksheet_name]
            worksheet.cell(
                1,
                1,
                f"Time - {time} | # {users_n}",
            )

            # HEADER FORMAT
            worksheet["A1"].font = Font(size=13, bold=True, color="00FF0000")

            # INDEX ALIGNMENT
            for row in worksheet[worksheet.min_row : worksheet.max_row]:
                cell = row[0]  # column A
                cell.alignment = Alignment(horizontal="left")
                cell = row[users_n + 2]  # column note
                cell.alignment = Alignment(horizontal="left")
                cells = row[1 : users_n + 2]  # from column B to note-1
                for cell in cells:
                    cell.alignment = Alignment(horizontal="center")

            # AUTO SIZE
            # Set auto-size for all columns
            # Use end +1 for ID column, and +2 for 'total' and 'note' columns
            column_letters = get_column_interval(start=1, end=users_n + 1 + 2)
            # Get columns
            columns = worksheet[column_letters[0] : column_letters[-1]]
            for column_letter, column in zip(column_letters, columns):
                # Instantiate max length then loop on cells to find max value
                max_length = 0
                # Cell loop
                for cell in column:
                    log.debug(
                        f"autosize for cell {cell.coordinate} with value '{cell.value}'"
                    )
                    try:  # Necessary to avoid error on empty cells
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                            log.debug(f"new max length set to {max_length}")
                    except Exception:
                        log.debug("empty cell")
                log.debug(f"final max length is {max_length}")
                adjusted_width = (max_length + 2) * 0.85
                log.debug(
                    f"adjusted width for column '{column_letter}' is {adjusted_width}"
                )
                worksheet.column_dimensions[column_letter].width = (
                    adjusted_width
                )
            # Since grouping fix width equal to first column width (openpyxl
            # bug), set first column of users' order equal to max width of
            # all users columns to avoid issues
            max_width = 0
            log.debug(
                f"find max width for users' columns '{column_letters[1]}:{column_letters[-3]}'"
            )
            for column_letter in column_letters[1:-2]:
                max_width = max(
                    max_width, worksheet.column_dimensions[column_letter].width
                )
            log.debug(f"max width for first users' columns is {max_width}")
            worksheet.column_dimensions[column_letters[1]].width = max_width

            # GROUPING
            # Group and hide columns, leave only ID, total and note
            column_letters = get_column_interval(start=2, end=users_n + 1)
            worksheet.column_dimensions.group(
                column_letters[0], column_letters[-1], hidden=True
            )

            # Close and reset bytes_io for the next dataframe
            writer.close()  # Important!
            bytes_io.seek(0)  # Important!

        # Message prompt
        pn.state.notifications.success(
            "File with orders downloaded",
            duration=config.panel.notifications.duration,
        )
        log.info("xlsx downloaded")
    else:
        gi.dataframe.value.drop(columns=["order"]).to_excel(
            writer, sheet_name="MENU", index=False
        )
        writer.close()  # Important!
        bytes_io.seek(0)  # Important!
        # Message prompt
        pn.state.notifications.warning(
            "No order<br>Menu downloaded",
            duration=config.panel.notifications.duration,
        )
        log.warning(
            "no order, menu exported to excel in place of orders' list"
        )

    return bytes_io


def submit_password(gi: gui.GraphicInterface, config: DictConfig) -> bool:
    """Same as backend_submit_password with an additional check on old
    password.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).

    Returns:
        bool: true if successful, false otherwise.
    """
    # Get user's password hash
    password_hash = auth.get_hash_from_user(pn_user(config), config=config)
    # Get username, updated updated at each key press
    old_password_key_press = gi.password_widget._widgets[
        "old_password"
    ].value_input
    # Check if old password is correct
    if password_hash == old_password_key_press:
        # Check if new password match repeat password
        return backend_submit_password(
            gi=gi, config=config, user=pn_user(config), logout_on_success=True
        )
    else:
        pn.state.notifications.error(
            "Incorrect old password!",
            duration=config.panel.notifications.duration,
        )

    return False


def backend_submit_password(
    gi: gui.GraphicInterface | gui.BackendInterface,
    config: DictConfig,
    user: str = None,
    is_guest: bool | None = None,
    is_admin: bool | None = None,
    logout_on_success: bool = False,
) -> bool:
    """Submit password to database from backend but used also from frontend as
    part of `submit_password` function.

    When used for backend `is_guest` and `is_admin` are selected from a widget.
    When called from frontend they are `None` and the function read them from
    database using the user input.

    Args:
        gi (gui.GraphicInterface | gui.BackendInterface): graphic interface object (used to interact with Panel widgets).
        config (DictConfig): Hydra configuration dictionary.
        user (str, optional): username. Defaults to None.
        is_guest (bool | None, optional): guest flag (true if guest). Defaults to None.
        is_admin (bool | None, optional): admin flag (true if admin). Defaults to None.
        logout_on_success (bool, optional): set to true to force logout once the new password is set. Defaults to False.

    Returns:
        bool: true if successful, false otherwise.
    """
    # Check if user is passed, otherwise check if backend widget
    # (password_widget.object.user) is available
    if not user:
        username = gi.password_widget._widgets["user"].value_input
    else:
        username = user
    # Get all passwords, updated at each key press
    new_password_key_press = gi.password_widget._widgets[
        "new_password"
    ].value_input
    repeat_new_password_key_press = gi.password_widget._widgets[
        "repeat_new_password"
    ].value_input
    # Check if new password match repeat password
    if username:
        if new_password_key_press == repeat_new_password_key_press:
            # Check if new password is valid with regex
            if re.fullmatch(
                config.basic_auth.psw_regex,
                new_password_key_press,
            ):
                # If is_guest and is_admin are None (not passed) use the ones
                # already set for the user
                if is_guest is None:
                    is_guest = auth.is_guest(user=user, config=config)
                if is_admin is None:
                    is_admin = auth.is_admin(user=user, config=config)
                # Add a privileged users only if guest option is not active
                if not is_guest:
                    auth.add_privileged_user(
                        user=username,
                        is_admin=is_admin,
                        config=config,
                    )
                # Green light: update the password!
                auth.add_user_hashed_password(
                    user=username,
                    password=new_password_key_press,
                    config=config,
                )

                # Logout if requested
                if logout_on_success:
                    pn.state.notifications.success(
                        "Password updated<br>Logging out",
                        duration=config.panel.notifications.duration,
                    )
                    sleep(4)
                    auth.force_logout()
                else:
                    pn.state.notifications.success(
                        "Password updated",
                        duration=config.panel.notifications.duration,
                    )
                return True

            else:
                pn.state.notifications.error(
                    "Password requirements not satisfied<br>Check again!",
                    duration=config.panel.notifications.duration,
                )

        else:
            pn.state.notifications.error(
                "Password are different!",
                duration=config.panel.notifications.duration,
            )
    else:
        pn.state.notifications.error(
            "Missing user!",
            duration=config.panel.notifications.duration,
        )

    return False

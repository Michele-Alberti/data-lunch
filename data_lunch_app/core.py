import panel as pn
import pandas as pd
import pathlib
import logging
import socket
import subprocess
from . import __version__
from . import models
from omegaconf import DictConfig, OmegaConf
from bokeh.models.widgets.tables import CheckboxEditor
from io import BytesIO
from PIL import Image
from pytesseract import pytesseract
import random
import re
from sqlalchemy import func
from sqlalchemy.sql.expression import true as sql_true
from time import sleep

# Graphic interface imports (after class definition)
from . import gui

# Authentication
from . import auth

# LOGGER ----------------------------------------------------------------------
log = logging.getLogger(__name__)


# FUNCTIONS -------------------------------------------------------------------


def get_host_name(config: DictConfig):
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


def delete_files(config: DictConfig):
    # Delete menu file if exist (every extension)
    files = list(
        pathlib.Path(config.db.shared_data_folder).glob(
            config.panel.file_name + "*"
        )
    )
    log.info(f"delete files {', '.join([f.name for f in files])}")
    for file in files:
        file.unlink(missing_ok=True)


def clean_tables(config: DictConfig):
    # Clean tables
    session = models.create_session(config)
    # Clean orders
    num_rows_deleted = session.query(models.Orders).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'orders'")
    # Clean menu
    num_rows_deleted = session.query(models.Menu).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'menu'")
    # Clean users
    num_rows_deleted = session.query(models.Users).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'users'")
    # Clean flags
    models.set_flag(config=config, id="no_more_orders", value=False)
    log.info("reset values in table 'flags'")


def set_guest_user_password(config: DictConfig) -> str:
    """If guest user is requested return a password, otherwise return ""
    This function always returns "" if basic auth is not used
    """
    if config.panel.guest_user and auth.is_basic_auth_active(config=config):
        # If flag does not exist use the default value
        if (
            models.get_flag(config=config, id="reset_guest_user_password")
            is None
        ):
            models.set_flag(
                config=config,
                id="reset_guest_user_password",
                value=config.panel.default_reset_guest_user_password_flag,
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
                special_chars=config.panel.psw_special_chars
            )
            # Add hashed password to database
            auth.add_user_hashed_password(
                "guest", guest_password, config=config
            )
        else:
            # Load from database
            session = models.create_session(config)
            guest_password = (
                session.query(models.Credentials)
                .get("guest")
                .password_encrypted.decrypt()
            )
    else:
        guest_password = ""

    return guest_password


def build_menu(
    event,
    config: DictConfig,
    app: pn.Template,
    gi: gui.GraphicInterface,
) -> pd.DataFrame:
    # Hide messages
    gi.error_message.visible = False
    gi.confirm_message.visible = False

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
                    pd.DataFrame({"item": config.panel.menu_items_to_concat}),
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
                    pd.DataFrame({"item": config.panel.menu_items_to_concat}),
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
                config.db.menu_table, engine, index=False, if_exists="append"
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
    event,
    config: DictConfig,
    gi: gui.GraphicInterface,
) -> None:
    # Create session
    session = models.create_session(config)

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

    # Guest graphic configuration
    if auth.is_guest(user=pn.state.user, config=config):
        # If guest show guest type selection group
        gi.person_widget.widgets["guest"].disabled = False
        gi.person_widget.widgets["guest"].visible = True
    else:
        # If authenticated users hide guest type selection group
        gi.person_widget.widgets["guest"].disabled = True
        gi.person_widget.widgets["guest"].visible = False

    # Reload menu
    engine = models.create_engine(config)
    df = pd.read_sql_table("menu", engine, index_col="id")
    df["order"] = False
    gi.dataframe.value = df
    gi.dataframe.formatters = {"order": {"type": "tickCross"}}
    gi.dataframe.editors = {
        "id": None,
        "item": None,
        "order": CheckboxEditor(),
    }

    if gi.toggle_no_more_order_button.value:
        gi.dataframe.hidden_columns = ["order"]
        gi.dataframe.disabled = True
    else:
        gi.dataframe.hidden_columns = []
        gi.dataframe.disabled = False

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
                for user in session.query(models.Users)
                .filter(models.Users.guest == guest_type)
                .all()
            ]
        # Loop through lunch times
        for time, df in df_dict.items():
            # Find the number of grumbling stomachs
            grumbling_stomachs = len(
                [
                    c
                    for c in df.columns
                    if c.lower() != config.panel.gui.total_column_name
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
                        config.panel.gui.takeaway_class_res_col, resolve=True
                    ),
                    "stylesheets": [config.panel.gui.css_files.labels_path],
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
                        config.panel.gui.takeaway_class_time_col, resolve=True
                    ),
                    "stylesheets": [config.panel.gui.css_files.labels_path],
                }
            else:
                res_col_label_kwargs = {
                    "time": time,
                    "diners_n": grumbling_stomachs,
                    "emoji": random.choice(config.panel.gui.food_emoji),
                    "css_classes": OmegaConf.to_container(
                        config.panel.gui.time_class_res_col, resolve=True
                    ),
                    "stylesheets": [config.panel.gui.css_files.labels_path],
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
                    "stylesheets": [config.panel.gui.css_files.labels_path],
                }
            # Add text to result column
            gi.res_col.append(pn.Spacer(height=10))
            gi.res_col.append(gi.build_time_label(**res_col_label_kwargs))
            # Add non editable table to result column
            gi.res_col.append(
                gi.build_order_table(
                    config, df=df, time=time, guests_lists=guests_lists
                )
            )
            # Add also a label to lunch time column
            gi.time_col.append(gi.build_time_label(**time_col_label_kwargs))

    log.debug("results reloaded")

    # Clean stats column
    gi.sidebar_stats_col.clear()
    # Update stats
    # Find how many people eat today (total number) and add value to database
    # stats table (when adding a stats if guest is not specified None is used
    # as default)
    today_locals_count = (
        session.query(func.count(models.Users.id))
        .filter(models.Users.guest == "NotAGuest")
        .scalar()
    )
    new_stat = models.Stats(hungry_people=today_locals_count)
    session.add(new_stat)
    # For each guest type find how many guests eat today
    for guest_type in config.panel.guest_types:
        today_guests_count = (
            session.query(func.count(models.Users.id))
            .filter(models.Users.guest == guest_type)
            .scalar()
        )
        new_stat = models.Stats(
            guest=guest_type, hungry_people=today_guests_count
        )
        session.add(new_stat)
    # Commit stats
    session.commit()

    # Group stats by month and return how many people had lunch
    df_stats = pd.read_sql_query(
        config.panel.stats_query,
        engine,
    )
    # Stats top text
    stats_text = gi.build_stats_text(
        df_stats=df_stats,
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
    gi.sidebar_stats_col.append(stats_text["stats"])
    gi.sidebar_stats_col.append(gi.stats_widget)
    gi.sidebar_stats_col.append(stats_text["info"])
    log.debug("stats updated")


def send_order(
    event,
    config: DictConfig,
    app: pn.Template,
    person: gui.Person,
    gi: gui.GraphicInterface,
) -> None:
    # Hide messages
    gi.error_message.visible = False
    gi.confirm_message.visible = False

    # Create session
    session = models.create_session(config)

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

    # If auth is active, check if a guests is using a name reserved to an
    # authenticated user
    if (
        auth.is_guest(user=pn.state.user, config=config)
        and (person.username in auth.list_users(config=config))
        and (auth.is_auth_active(config=config))
    ):
        pn.state.notifications.error(
            f"{person.username} is a reserved name<br>Please choose a different one",
            duration=config.panel.notifications.duration,
        )

        # Reload the menu
        reload_menu(
            None,
            config,
            gi,
        )

        return

    # Check if an authenticated user is ordering for an invalid name
    if (
        not auth.is_guest(user=pn.state.user, config=config)
        and (
            person.username
            not in (
                name
                for name in auth.list_users(config=config)
                if name != "guest"
            )
        )
        and (auth.is_auth_active(config=config))
    ):
        pn.state.notifications.error(
            f"{person.username} is not a valid name<br>for an authenticated user<br>Please choose a different one",
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
    if person.username and not df_order.empty:
        # Check if the user already placed an order
        if session.query(models.Users).get(person.username):
            pn.state.notifications.warning(
                f"Cannot overwrite an order<br>Delete {person.username}'s order first and retry",
                duration=config.panel.notifications.duration,
            )
            log.warning(f"an order already exist for {person.username}")
        else:
            # Place order
            try:
                # Add User (note is empty by default)
                # Do not pass guest for authenticated users (default to NotAGuest)
                if auth.is_guest(user=pn.state.user, config=config):
                    new_user = models.Users(
                        id=person.username,
                        guest=person.guest,
                        takeaway=person.takeaway,
                        note=person.note,
                    )
                else:
                    new_user = models.Users(
                        id=person.username,
                        takeaway=person.takeaway,
                        note=person.note,
                    )
                session.add(new_user)
                # Add orders as long table (one row for each item selected by a user)
                for index, row in df_order.iterrows():
                    # Order
                    new_order = models.Orders(
                        user=person.username,
                        lunch_time=person.lunch_time,
                        menu_item_id=index,
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
                    "Order sent", duration=config.panel.notifications.duration
                )
                log.info(f"{person.username}'s order saved")
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
                log.warning("database error")
                # Open modal window
                app.open_modal()
    else:
        if not person.username:
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
    event,
    config: DictConfig,
    app: pn.Template,
    person: gui.Person,
    gi: gui.GraphicInterface,
) -> None:
    # Hide messages
    gi.error_message.visible = False
    gi.confirm_message.visible = False

    # Create session
    session = models.create_session(config)

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

    if person.username:
        # If auth is active, check if a guests is deleting an order of an
        # authenticated user
        if (
            auth.is_guest(user=pn.state.user, config=config)
            and (person.username in auth.list_users(config=config))
            and (auth.is_auth_active(config=config))
        ):
            pn.state.notifications.error(
                f"You are not authorized<br>to delete<br>{person.username}'s order",
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
        num_rows_deleted_users = (
            session.query(models.Users)
            .filter(models.Users.id == person.username)
            .delete()
        )
        # Delete also orders (hotfix for Debian)
        num_rows_deleted_orders = (
            session.query(models.Orders)
            .filter(models.Orders.user == person.username)
            .delete()
        )
        session.commit()
        if (num_rows_deleted_users > 0) or (num_rows_deleted_orders > 0):
            # Update dataframe widget
            reload_menu(
                None,
                config,
                gi,
            )

            pn.state.notifications.success(
                "Order canceled", duration=config.panel.notifications.duration
            )
            log.info(f"{person.username}'s order canceled")
        else:
            pn.state.notifications.warning(
                f'No order for user named<br>"{person.username}"',
                duration=config.panel.notifications.duration,
            )
            log.info(f"no order for user named {person.username}")
    else:
        pn.state.notifications.warning(
            "Please insert user name",
            duration=config.panel.notifications.duration,
        )
        log.warning("missing username")


def df_list_by_lunch_time(
    config: DictConfig,
) -> dict:
    # Create database engine and session
    engine = models.create_engine(config)
    # Read menu and save how menu items are sorted (first courses, second courses, etc.)
    original_order = pd.read_sql_table("menu", engine, index_col="id").item
    # Create session
    session = models.create_session(config)
    # Build takeaway list
    takeaway_list = [
        user.id
        for user in session.query(models.Users)
        .filter(models.Users.takeaway == sql_true())
        .all()
    ]
    # Read dataframe
    df = pd.read_sql_query(config.panel.orders_query, engine)
    # Build a dict of dataframes, one for each lunch time
    df_dict = {}
    for time in df.lunch_time.sort_values().unique():
        # Take only one lunch time
        temp_df = (
            df[df.lunch_time == time]
            .drop(columns="lunch_time")
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

        def clean_up_table(config, df_in):
            # Add columns of totals
            df = df_in.copy()
            df[config.panel.gui.total_column_name] = df.sum(axis=1)
            if config.panel.drop_unused_menu_items:
                df = df[df[config.panel.gui.total_column_name] > 0]
            # Find users included in this lunch time
            users = df.columns
            # Find relevant notes
            session = models.create_session(config)
            user_data = (
                session.query(models.Users)
                .filter(models.Users.id.in_(users))
                .all()
            )
            # Add notes
            for user in user_data:
                df.loc["NOTE", user.id] = user.note
            # Change NaNs to '-'
            df = df.fillna("-")

            return df

        # Clean and add resulting dataframes to dict
        # RESTAURANT LUNCH
        if not df_users_restaurant.empty:
            df_users_restaurant = clean_up_table(config, df_users_restaurant)
            df_dict[time] = df_users_restaurant
        # TAKEAWAY
        if not df_users_takeaways.empty:
            df_users_takeaways = clean_up_table(config, df_users_takeaways)
            df_dict[
                f"{time} {config.panel.gui.takeaway_id}"
            ] = df_users_takeaways

    return df_dict


def download_dataframe(
    config: DictConfig,
    app: pn.Template,
    gi: gui.GraphicInterface,
) -> None:
    # Hide messages
    gi.error_message.visible = False
    gi.confirm_message.visible = False

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
            df.to_excel(writer, sheet_name=time.replace(":", "."), startrow=1)
            writer.sheets[time.replace(":", ".")].cell(
                1,
                1,
                f"Time - {time} | # {len([c for c in df.columns if c != config.panel.gui.total_column_name])}",
            )
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
        writer.save()  # Important!
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
    password"""
    # Get user's password hash
    password_hash = auth.get_hash_from_user(pn.state.user, config=config)
    # Check if old password is correct
    if password_hash == gi.password_widget.object.old_password:
        # Check if new password match repeat password
        return backend_submit_password(
            gi=gi, config=config, user=pn.state.user, logout_on_success=True
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
    part of submit_password function.
    When used for backend is_guest and is_admin are selected from a widget.
    When called from frontend they are None and the function read them from
    database using the user input.
    """
    # Check if user is passed, otherwise check if backend widget
    # (password_widget.object.user) is available
    if not user:
        username = gi.password_widget.object.user
    else:
        username = user
    # Check if new password match repeat password
    if username:
        if (
            gi.password_widget.object.new_password
            == gi.password_widget.object.repeat_new_password
        ):
            # Check if new password is valid with regex
            if re.fullmatch(
                config.panel.psw_regex, gi.password_widget.object.new_password
            ):
                # If is_guest and is_admin are None (not passed) use the ones
                # already set for the user
                if is_guest is None:
                    is_guest = auth.is_guest(user=user, config=config)
                if is_admin is None:
                    is_admin = auth.is_admin(user=user, config=config)
                # Add an authorized users only if guest option is not active
                if not is_guest:
                    auth.add_authorized_user(
                        user=username,
                        is_admin=is_admin,
                        config=config,
                    )
                # Green light: update the password!
                auth.add_user_hashed_password(
                    user=username,
                    password=gi.password_widget.object.new_password,
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

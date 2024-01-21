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
from sqlalchemy import func, select, delete
from sqlalchemy.sql.expression import true as sql_true
from time import sleep

# Graphic interface imports (after class definition)
from . import gui

# Authentication
from . import auth
from .auth import pn_user
import cryptography.fernet

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
    """If guest user is requested return a password, otherwise return ""
    This function always returns "" if basic auth is not used
    """
    # Check if basic auth is active
    if auth.is_basic_auth_active(config=config):
        # If active basic_auth.guest_user is true if guest user is active
        is_guest_user_active = config.basic_auth.guest_user
    else:
        # Otherwise the guest user feature is not applicable
        is_guest_user_active = False

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
    event,
    config: DictConfig,
    gi: gui.GraphicInterface,
) -> None:
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

        # Set no more orders toggle button visibility and activation
        if auth.is_guest(
            user=pn_user(config), config=config, allow_override=False
        ):
            # Deactivate the no_more_orders button for guest users
            gi.toggle_no_more_order_button.disabled = True
            gi.toggle_no_more_order_button.visible = False
        else:
            # Activate the no_more_orders button for privileged users
            gi.toggle_no_more_order_button.disabled = False
            gi.toggle_no_more_order_button.visible = True

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
                gi.res_col.append(pn.Spacer(height=10))
                gi.res_col.append(gi.build_time_label(**res_col_label_kwargs))
                # Add non editable table to result column
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

        # Check if a privileged user is ordering for an invalid name
        if (
            not auth.is_guest(user=pn_user(config), config=config)
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
                f"{person.username} is not a valid name<br>for a privileged user<br>Please choose a different one",
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
            if session.get(models.Users, person.username):
                pn.state.notifications.warning(
                    f"Cannot overwrite an order<br>Delete {person.username}'s order first and retry",
                    duration=config.panel.notifications.duration,
                )
                log.warning(f"an order already exist for {person.username}")
            else:
                # Place order
                try:
                    # Add User (note is empty by default)
                    # Do not pass guest for privileged users (default to NotAGuest)
                    if auth.is_guest(user=pn_user(config), config=config):
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
                        "Order sent",
                        duration=config.panel.notifications.duration,
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

        if person.username:
            # If auth is active, check if a guests is deleting an order of a
            # privileged user
            if (
                auth.is_guest(user=pn_user(config), config=config)
                and (person.username in auth.list_users(config=config))
                and (auth.is_auth_active(config=config))
            ):
                pn.state.notifications.error(
                    f"You do not have enough privileges<br>to delete<br>{person.username}'s order",
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
            num_rows_deleted_users = session.execute(
                delete(models.Users).where(models.Users.id == person.username)
            )
            # Delete also orders (hotfix for Debian)
            num_rows_deleted_orders = session.execute(
                delete(models.Orders).where(
                    models.Orders.user == person.username
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
    # Read dataframe
    df = pd.read_sql_query(
        config.db.orders_query.format(
            schema=config.db.get("schema", models.SCHEMA)
        ),
        engine,
    )
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

            with session:
                user_data = session.scalars(
                    select(models.Users).where(models.Users.id.in_(users))
                ).all()
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
    password"""
    # Get user's password hash
    password_hash = auth.get_hash_from_user(pn_user(config), config=config)
    # Check if old password is correct
    if password_hash == gi.password_widget.object.old_password:
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
                config.basic_auth.psw_regex,
                gi.password_widget.object.new_password,
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

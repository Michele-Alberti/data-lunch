from xml.parsers.expat import model
import panel as pn
import param
import panel.widgets as pnw
import pandas as pd
import pathlib
from panel.widgets import Tqdm
import logging
import socket
import subprocess
from . import __version__
from . import models
from omegaconf import DictConfig
from bokeh.models.widgets.tables import CheckboxEditor
from io import BytesIO
from PIL import Image
from pytesseract import pytesseract
from sqlalchemy import func
from sqlalchemy.sql.expression import true as sql_true
import random

# LOGGER ----------------------------------------------------------------------
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
    num_rows_deleted = session.query(models.Flags).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'flags'")


def build_menu(
    event,
    config: DictConfig,
    app: pn.Template,
    file_widget: pnw.FileInput,
    dataframe_widget: pnw.DataFrame,
    stats_col: pn.Column,
    res_col: pn.Column,
    time_col: pn.Column,
    no_more_order: pnw.Toggle,
    messages: list[pn.pane.HTML],
) -> pd.DataFrame:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    # Build image path
    menu_filename = str(
        pathlib.Path(config.db.shared_data_folder) / config.panel.file_name
    )

    # Delete menu file if exist (every extension)
    delete_files(config)

    # Load file from widget
    if file_widget.value is not None:
        # Find file extension
        file_ext = pathlib.PurePath(file_widget.filename).suffix

        # Save file locally
        local_menu_filename = menu_filename + file_ext
        file_widget.save(local_menu_filename)

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
                "",
                config,
                dataframe_widget,
                stats_col,
                res_col,
                time_col,
                no_more_order,
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
            error_message.object = f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
            error_message.visible = True
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
    dataframe_widget: pnw.DataFrame,
    stats_col: pn.Column,
    res_col: pn.Column,
    time_col: pn.Column,
    no_more_order: pnw.Toggle,
) -> None:

    # Create session
    session = models.create_session(config)

    # Check if someone changed the "no_more_order" toggle
    if no_more_order.value != models.get_flag(
        session=session, id="no_more_orders"
    ):
        # The following statement will trigger the toggle callback
        # which will call reload_menu once again
        # This is the reason why this if contains a return (without the return
        # the content will be reloaded twice)
        no_more_order.value = models.get_flag(
            session=session, id="no_more_orders"
        )

        return

    # Reload menu
    engine = models.create_engine(config)
    df = pd.read_sql_table("menu", engine, index_col="id")
    df["order"] = False
    dataframe_widget.value = df
    dataframe_widget.formatters = {"order": {"type": "tickCross"}}
    dataframe_widget.editors = {
        "id": None,
        "item": None,
        "order": CheckboxEditor(),
    }

    if no_more_order.value:
        dataframe_widget.hidden_columns = ["order"]
        dataframe_widget.disabled = True
    else:
        dataframe_widget.hidden_columns = []
        dataframe_widget.disabled = False

    log.debug("menu reloaded")

    # Load results
    df_dict = df_list_by_lunch_time(config)
    # Clean columns and load text and dataframes
    res_col.clear()
    time_col.clear()
    if df_dict:
        res_col.append(config.panel.result_column_text)
        time_col.append(
            pn.pane.Markdown(
                config.panel.time_column_text,
                sizing_mode="stretch_width",
                style={"text-align": "center", "display": "block"},
            )
        )
        # Build guests list
        guests_list = [
            user.id
            for user in session.query(models.Users)
            .filter(models.Users.guest == sql_true())
            .all()
        ]
        # Loop through lunch times
        for time, df in df_dict.items():
            # Find the number of grumbling stomachs
            grumbling_stomachs = len(
                [
                    c
                    for c in df.columns
                    if c.lower() != config.panel.total_column_name
                ]
            )
            # Add text to result column
            res_col.append(pn.Spacer(height=10))
            res_col.append(
                pn.pane.HTML(
                    f"{time} &#10072; {random.choice(food_emoji)} &#10006; {grumbling_stomachs}",
                    style=dict(config.panel.time_style_res_col),
                )
            )
            # Add a receipt symbol for guest users
            df.columns = [
                f"{c} 💰"
                if (c in guests_list) and (c != config.panel.total_column_name)
                else c
                for c in df.columns
            ]
            # Add non editable table to result column
            orders_table_widget = pnw.Tabulator(
                name=time,
                value=df,
                frozen_columns=[0],
                sizing_mode="stretch_width",
                layout="fit_data_stretch",
            )
            orders_table_widget.editors = {c: None for c in df.columns}
            res_col.append(orders_table_widget)
            # Add also a label to lunch time column
            time_col.append(
                pn.pane.HTML(
                    f"{time}<br>&#127860;&#10006; {grumbling_stomachs}&nbsp",
                    style=dict(config.panel.time_style_time_col),
                    align=("center", "center"),
                )
            )

    log.debug("results reloaded")

    # Clean stats column
    stats_col.clear()
    # Update stats
    # Find how many people eat today and add value to database stats table
    today_count = session.query(func.count(models.Users.id)).scalar()
    today_guests_count = (
        session.query(func.count(models.Users.id))
        .filter(models.Users.guest == sql_true())
        .scalar()
    )
    new_stat = models.Stats(
        hungry_people=today_count, hungry_guests=today_guests_count
    )
    session.add(new_stat)
    session.commit()

    # Group stats by month and return how many people had lunch
    df_stats = pd.read_sql_query(
        config.panel.stats_query,
        engine,
        # index_col=list(config.panel.stats_id_cols),
    )
    # Stats top text
    stats_text = pn.pane.HTML(
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
    other_info_text = pn.pane.HTML(
        f"""
        <h4>Other Info</h3>
        <div>
            <i class="fa-solid fa-tag" style="font-size: 1.15rem;"></i>&nbsp;<strong>Version:</strong> <i>{__version__}</i>
            <br>
            <i class="fa-solid fa-microchip" style="font-size: 1.15rem;"></i>&nbsp;<strong>Host:</strong> <i>{get_host_name(config)}</i>
        </div>
        """,
        sizing_mode="stretch_width",
    )
    # Create stats table (non-editable)
    stats_widget = pnw.Tabulator(
        name="Statistics",
        hidden_columns=["index"],
        width=sidebar_width - 20,
        layout="fit_columns",
    )
    stats_widget.editors = {c: None for c in df_stats.columns}
    stats_widget.value = df_stats
    stats_col.append(stats_text)
    stats_col.append(stats_widget)
    stats_col.append(other_info_text)
    log.debug("stats updated")


def send_order(
    event,
    config: DictConfig,
    app: pn.Template,
    person: Person,
    dataframe_widget: pnw.DataFrame,
    stats_col: pn.Column,
    res_col: pn.Column,
    time_col: pn.Column,
    no_more_order: pnw.Toggle,
    messages: list[pn.pane.HTML],
) -> None:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    # Create session
    session = models.create_session(config)

    # Check if the "no more order" toggle button is pressed
    if models.get_flag(session=session, id="no_more_orders"):
        pn.state.notifications.error(
            "It is not possible to place new orders",
            duration=config.panel.notifications.duration,
        )

        # Reload the menu
        reload_menu(
            "",
            config,
            dataframe_widget,
            stats_col,
            res_col,
            time_col,
            no_more_order,
        )

        return

    # Write order into database table
    df = dataframe_widget.value.copy()
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
                # Add User (note is empty by default, guest is false
                # by default)
                new_user = models.Users(
                    id=person.username,
                    guest=person.guest,
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
                    "",
                    config,
                    dataframe_widget,
                    stats_col,
                    res_col,
                    time_col,
                    no_more_order,
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
                error_message.object = (
                    f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
                )
                error_message.visible = True
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
    person: Person,
    dataframe_widget: pnw.DataFrame,
    stats_col: pn.Column,
    res_col: pn.Column,
    time_col: pn.Column,
    no_more_order: pnw.Toggle,
    messages: list[pn.pane.HTML],
) -> None:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    # Create session
    session = models.create_session(config)

    # Check if the "no more order" toggle button is pressed
    if models.get_flag(session=session, id="no_more_orders"):
        pn.state.notifications.error(
            "It is not possible to delete orders",
            duration=config.panel.notifications.duration,
        )

        # Reload the menu
        reload_menu(
            "",
            config,
            dataframe_widget,
            stats_col,
            res_col,
            time_col,
            no_more_order,
        )

        return

    if person.username:
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
                "",
                config,
                dataframe_widget,
                stats_col,
                res_col,
                time_col,
                no_more_order,
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
        # Add columns of totals
        df_users[config.panel.total_column_name] = df_users.sum(axis=1)
        if config.panel.drop_unused_menu_items:
            df_users = df_users[df_users[config.panel.total_column_name] > 0]
        # Add notes
        # Find users included in this lunch time
        users = tuple(temp_df.user.unique())
        # Find relevant notes
        session = models.create_session(config)
        user_data = (
            session.query(models.Users)
            .filter(models.Users.id.in_(users))
            .all()
        )
        for user in user_data:
            df_users.loc["NOTE", user.id] = user.note
        # Change NaNs to '-'
        df_users = df_users.fillna("-")
        # Add resulting dataframe to dict
        df_dict[time] = df_users

    return df_dict


def download_dataframe(
    config: DictConfig,
    app: pn.Template,
    dataframe_widget: pnw.DataFrame,
    messages: list[pn.pane.HTML],
) -> None:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

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
            df.to_excel(writer, sheet_name=time.replace(":", "."))
            writer.save()  # Important!
            bytes_io.seek(0)  # Important!

        # Message prompt
        pn.state.notifications.success(
            "File with orders downloaded",
            duration=config.panel.notifications.duration,
        )
        log.info("xlsx downloaded")
    else:
        dataframe_widget.value.drop(columns=["order"]).to_excel(
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

from xml.parsers.expat import model
import panel as pn
import param
import panel.widgets as pnw
import pandas as pd
import pathlib
from panel.widgets import Tqdm
import logging
from . import models
from omegaconf import DictConfig
from bokeh.models.widgets.tables import CheckboxEditor
from io import BytesIO
from PIL import Image
from pytesseract import pytesseract

# LOGGER ----------------------------------------------------------------------
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

    def __init__(self, config, **params):
        super().__init__(**params)
        self.param["lunch_time"].objects = config.panel.lunch_times_options

    def __str__(self):
        return f"PERSON:{self.name}"


# FUNCTIONS -------------------------------------------------------------------
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
    num_rows_deleted = session.query(models.Menu).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'menu'")
    num_rows_deleted = session.query(models.Orders).delete()
    session.commit()
    log.info(f"deleted {num_rows_deleted} from table 'orders'")


def build_menu(
    event,
    config: DictConfig,
    app: pn.Template,
    file_widget: pnw.FileInput,
    dataframe_widget: pnw.DataFrame,
    res_col: pn.Column,
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

    # Load image from widget
    if file_widget.value is not None:
        # Find file extension
        file_ext = pathlib.PurePath(file_widget.filename).suffix

        # Save file locally
        local_menu_filename = menu_filename + file_ext
        file_widget.save(local_menu_filename)

        # Clean tables
        clean_tables(config)

        # File can be either an excel file or an image
        if file_ext == ".png" or file_ext == ".jpg":
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
            error_message.object = "WRONG FILE TYPE"
            error_message.visible = True
            log.warning("wrong file type")

        # Upload to database menu table
        engine = models.create_engine(config)
        try:
            df.drop_duplicates(subset="item").to_sql(
                config.db.menu_table, engine, index=False, if_exists="append"
            )
            # Update dataframe widget
            reload_menu("", config, dataframe_widget, res_col)

            confirm_message.object = "MENU UPLOADED"
            confirm_message.visible = True
            log.info("menu uploaded")
        except Exception as e:
            # Any exception here is a database fault
            error_message.object = f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
            error_message.visible = True
            log.warning("database error")

    else:
        error_message.object = "NO FILE SELECTED"
        error_message.visible = True
        log.warning("no image selected")

    # Open modal window
    app.open_modal()


def reload_menu(
    event,
    config: DictConfig,
    dataframe_widget: pnw.DataFrame,
    res_col: pn.Column,
) -> None:
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

    log.debug("menu reloaded")

    # Load results
    df_dict = df_list_by_lunch_time(config)
    # Clean column and load text and dataframes
    res_col.clear()
    res_col.append(pn.Spacer(height=50))
    res_col.append(config.panel.result_column_text)
    if df_dict:
        for time, df in df_dict.items():
            res_col.append(pn.Spacer(height=25))
            res_col.append(f"### {time}")
            res_col.append(pnw.Tabulator(name=time, value=df))

    log.debug("results reloaded")


def send_order(
    event,
    config: DictConfig,
    app: pn.Template,
    person: Person,
    dataframe_widget: pnw.DataFrame,
    res_col: pn.Column,
    messages: list[pn.pane.HTML],
) -> None:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    # Write order into database table
    df = dataframe_widget.value.copy()
    df_order = df[df.order]

    # If no username is missing or the order is empty return an error message
    if person.username and not df_order.empty:
        session = models.create_session(config)
        # Check if the user already placed an order
        if (
            session.query(models.Orders)
            .filter(models.Orders.user == person.username)
            .first()
        ):
            error_message.object = f'CANNOT OVERWRITE AN ORDER<br><br>You have to first delete the order for user named "{person.username}"'
            error_message.visible = True
            log.warning("database error")
        else:
            # Place order
            try:
                for index, row in df_order.iterrows():
                    new_order = models.Orders(
                        user=person.username,
                        lunch_time=person.lunch_time,
                        menu_item_id=index,
                    )
                    session.add(new_order)
                    session.commit()

                # Update dataframe widget
                reload_menu("", config, dataframe_widget, res_col)

                confirm_message.object = "ORDER SENT"
                confirm_message.visible = True
                log.info(f"{person.username}'s order saved")
            except Exception as e:
                # Any exception here is a database fault
                error_message.object = (
                    f"DATABASE ERROR<br><br>ERROR:<br>{str(e)}"
                )
                error_message.visible = True
                log.warning("database error")
    else:
        if not person.username:
            error_message.object = "PLEASE INSERT USER NAME"
            error_message.visible = True
            log.warning("missing username")
        else:
            error_message.object = "PLEASE MAKE A SELECTION"
            error_message.visible = True
            log.warning("no selection made")

    # Open modal window
    app.open_modal()


def delete_order(
    event,
    config: DictConfig,
    app: pn.Template,
    person: Person,
    dataframe_widget: pnw.DataFrame,
    res_col: pn.Column,
    messages: list[pn.pane.HTML],
) -> None:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    if person.username:
        session = models.create_session(config)
        num_rows_deleted = (
            session.query(models.Orders)
            .filter(models.Orders.user == person.username)
            .delete()
        )
        session.commit()
        if num_rows_deleted > 0:
            # Update dataframe widget
            reload_menu("", config, dataframe_widget, res_col)

            confirm_message.object = "ORDER CANCELED"
            confirm_message.visible = True
            log.info(f"{person.username}'s order canceled")
        else:
            confirm_message.object = f'NO ORDER<br><br>No order exists for user named "{person.username}"'
            confirm_message.visible = True
            log.info(f"{person.username}'s order canceled")
    else:
        error_message.object = "PLEASE INSERT USER NAME"
        error_message.visible = True
        log.warning("missing username")

    # Open modal window
    app.open_modal()


def df_list_by_lunch_time(
    config: DictConfig,
) -> dict:

    # Create database engine and session
    engine = models.create_engine(config)
    # Read menu
    original_order = pd.read_sql_table("menu", engine, index_col="id").item
    # Read dataframe
    df = pd.read_sql_query(config.panel.orders_query, engine)
    # Build a list of dataframes, one for each lunch time
    df_dict = {}
    for time in df.lunch_time.unique():
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
        # Reorder index in accordance with original menu and add columns of totals
        df_users = df_users.reindex(original_order)
        df_users["totale"] = df_users.sum(axis=1)
        df_dict[time] = df_users

    return df_dict


def download_dataframe(
    config: DictConfig,
    app: pn.Template,
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
    for time, df in df_dict.items():
        log.info(f"writing sheet {time}")
        df.to_excel(writer, sheet_name=time.replace(":", "."))
        writer.save()  # Important!
        bytes_io.seek(0)  # Important!

    # Message prompt
    confirm_message.object = "FILE WITH ORDERS DOWNLOADED"
    confirm_message.visible = True
    log.info("xlsx downloaded")

    # Open modal window
    app.open_modal()

    return bytes_io

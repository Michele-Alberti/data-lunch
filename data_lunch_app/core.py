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

# LOGGER ----------------------------------------------------------------------
log = logging.getLogger(__name__)

# OPTIONS AND DEFAULTS --------------------------------------------------------
# App
sidebar_width = 400


# CLASS -----------------------------------------------------------------------
class Person(param.Parameterized):

    username = param.String(default="", doc="your name")

    def __str__(self):
        return f"PERSON:{self.name}"


# FUNCTIONS -------------------------------------------------------------------
def build_menu(
    event,
    config: DictConfig,
    app: pn.Template,
    menu_image_widget: pnw.FileInput,
    dataframe_widget: pnw.DataFrame,
    messages: list[pn.pane.HTML],
) -> pd.DataFrame:
    # Expand messages
    error_message = messages[0]
    confirm_message = messages[1]
    # Hide messages
    error_message.visible = False
    confirm_message.visible = False

    # Build image path
    menu_image_filename = str(
        pathlib.Path(config.panel.shared_data_folder) / config.panel.image_name
    )

    # Delete image if exist
    image_path = pathlib.Path(menu_image_filename)
    image_path.unlink(missing_ok=True)

    # Load image from widget
    if menu_image_widget.value is not None:
        menu_image_widget.save(menu_image_filename)

        # Clean tables
        session = models.create_session(config)
        num_rows_deleted = session.query(models.Menu).delete()
        session.commit()
        log.info(f"deleted {num_rows_deleted} from table 'menu")
        num_rows_deleted = session.query(models.Orders).delete()
        session.commit()
        log.info(f"deleted {num_rows_deleted} from table 'orders")

        # Transform image into a pandas DataFrame
        # TODO

        # Upload to database menu table
        df = pd.DataFrame(
            {
                "item": [
                    "Pasta al sugo",
                    "Tacchino",
                    "Patate",
                    "Insalata",
                    "Torta",
                    "Caffé",
                ]
            }
        )
        engine = models.create_engine(config)
        df.to_sql(
            config.db.menu_table, engine, index=False, if_exists="append"
        )

        # Update dataframe widget
        reload_menu("", config, dataframe_widget)

        confirm_message.object = "MENU UPLOADED"
        confirm_message.visible = True
        log.info("menu uploaded")

    else:
        error_message.object = "NO IMAGE SELECTED"
        error_message.visible = True
        log.warning("no image selected")

    # Open modal window
    app.open_modal()


def reload_menu(
    event, config: DictConfig, dataframe_widget: pnw.DataFrame
) -> None:
    # Write order into database table

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


def send_order(
    event,
    config: DictConfig,
    app: pn.Template,
    person: Person,
    dataframe_widget: pnw.DataFrame,
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

    if person.username and not df_order.empty:
        session = models.create_session(config)
        for index, row in df_order.iterrows():
            new_order = models.Orders(user=person.username, menu_item_id=index)
            session.add(new_order)
            session.commit()
        confirm_message.object = "ORDER SENT"
        confirm_message.visible = True
        log.info(f"{person.username}'s order saved")
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
    # Create database engine
    engine = models.create_engine(config)
    # Read dataframe
    df = pd.read_sql_query(config.db.orders_query, engine)
    # Users' selections
    df_users = df.pivot_table(
        index="item", columns="user", aggfunc=len, fill_value=0
    )
    df_users = df_users.reindex(dataframe_widget.value.item)
    df_users["totale"] = df_users.sum(axis=1)
    # Export dataframe
    bytes_io = BytesIO()
    writer = pd.ExcelWriter(bytes_io)
    df_users.to_excel(writer)
    writer.save()  # Important!
    bytes_io.seek(0)  # Important!

    confirm_message.object = "FILE WITH ORDERS DOWNLOADED"
    confirm_message.visible = True
    log.info("xlsx downloaded")

    # Open modal window
    app.open_modal()

    return bytes_io

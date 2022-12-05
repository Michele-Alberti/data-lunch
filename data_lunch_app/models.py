import hydra
import logging
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Date,
    Boolean,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, Session
from omegaconf import DictConfig
from datetime import datetime

log = logging.getLogger(__name__)

# Create database instance (with lazy loading)
db = declarative_base()


# EVENTS ----------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# MODELS ----------------------------------------------------------------------


class Menu(db):
    __tablename__ = "menu"
    id = Column(Integer, primary_key=True)
    item = Column(String(250), unique=False, nullable=False)
    orders = relationship(
        "Orders",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<MENU_ITEM:{self.id} - {self.item}>"


class Orders(db):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user = Column(
        String(100),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    lunch_time = Column(String(7), index=True, nullable=False)
    menu_item_id = Column(
        Integer,
        ForeignKey("menu.id", ondelete="CASCADE"),
        nullable=False,
    )
    menu_item = relationship("Menu", back_populates="orders")
    note = relationship("Users", back_populates="orders", uselist=False)

    def __repr__(self):
        return f"<ORDER:{self.user}, {self.menu_item.item}>"


class Users(db):
    __tablename__ = "users"
    id = Column(
        String(100),
        primary_key=True,
        nullable=False,
    )
    guest = Column(Boolean, nullable=False, default=False)
    note = Column(String(500), unique=False, nullable=False)
    orders = relationship(
        "Orders",
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<NOTE:{self.id} - {self.user}>"


class Stats(db):
    __tablename__ = "stats"
    id = Column(
        Date,
        primary_key=True,
        nullable=False,
        default=datetime.utcnow(),
        sqlite_on_conflict_primary_key="REPLACE",
    )
    hungry_people = Column(Integer, nullable=False, default=0)
    hungry_guests = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<STAT:{self.id} - HP:{self.hungry_people}>"


# FUNCTIONS -------------------------------------------------------------------


def create_engine(config: DictConfig) -> Engine:
    """SQLAlchemy engine factory function"""
    engine = hydra.utils.instantiate(config.db.engine)

    return engine


def create_session(config: DictConfig) -> Session:
    """Database session factory function"""
    engine = create_engine(config)
    session = Session(engine)

    return session


def create_database(config: DictConfig):
    """Database factory function"""
    engine = create_engine(config)
    db.metadata.create_all(engine)

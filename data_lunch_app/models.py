import hydra
import logging
import pathlib
from sqlalchemy import (
    Column,
    PrimaryKeyConstraint,
    ForeignKey,
    Integer,
    String,
    TypeDecorator,
    Date,
    Boolean,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, validates, Session
from sqlalchemy.sql import func, elements
from sqlalchemy.sql import false as sql_false
from omegaconf import DictConfig
from datetime import datetime

# Authentication
from . import auth

log = logging.getLogger(__name__)

# Create database instance (with lazy loading)
Data = declarative_base()


# EVENTS ----------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


# CUSTOM COLUMNS --------------------------------------------------------------
class Password(TypeDecorator):
    """Allows storing and retrieving password hashes using PasswordHash."""

    impl = String

    def process_bind_param(
        self, value: auth.PasswordHash | str, dialect
    ) -> str:
        """Ensure the value is a PasswordHash and then return its hash."""
        return self._convert(value).hashed_password

    def process_result_value(
        self, value: str, dialect
    ) -> auth.PasswordHash | None:
        """Convert the hash to a PasswordHash, if it's non-NULL."""
        if value is not None:
            return auth.PasswordHash(value)

    def validator(
        self, password: auth.PasswordHash | str
    ) -> auth.PasswordHash:
        """Provides a validator/converter for @validates usage."""
        return self._convert(password)

    def _convert(self, value: auth.PasswordHash | str) -> auth.PasswordHash:
        """Returns a PasswordHash from the given string.

        PasswordHash instances or None values will return unchanged.
        Strings will be hashed and the resulting PasswordHash returned.
        Any other input will result in a TypeError.
        """
        if isinstance(value, auth.PasswordHash):
            return value
        elif isinstance(value, str):
            return auth.PasswordHash.from_str(value)
        elif value is not None:
            raise TypeError(
                f"Cannot initialize PasswordHash from type '{type(value)}'"
            )

        # Reached only if value is None
        return None


class Encrypted(TypeDecorator):
    """Allows storing and retrieving password hashes using PasswordHash."""

    impl = String

    def process_bind_param(
        self, value: auth.PasswordEncrypt | str, dialect
    ) -> str:
        """Ensure the value is a PasswordEncrypt and then return the encrypted password."""
        converted_value = self._convert(value)
        if converted_value:
            return converted_value.encrypted_password
        else:
            return None

    def process_result_value(
        self, value: str, dialect
    ) -> auth.PasswordEncrypt | None:
        """Convert the hash to a PasswordEncrypt, if it's non-NULL."""
        if value is not None:
            return auth.PasswordEncrypt(value)

    def validator(
        self, password: auth.PasswordEncrypt | str
    ) -> auth.PasswordEncrypt:
        """Provides a validator/converter for @validates usage."""
        return self._convert(password)

    def _convert(
        self, value: auth.PasswordEncrypt | str
    ) -> auth.PasswordEncrypt:
        """Returns a PasswordEncrypt from the given string.

        PasswordEncrypt instances or None values will return unchanged.
        Strings will be encrypted and the resulting PasswordEncrypt returned.
        Any other input will result in a TypeError.
        """
        if isinstance(value, auth.PasswordEncrypt):
            return value
        elif isinstance(value, str):
            return auth.PasswordEncrypt.from_str(value)
        elif value is not None:
            raise TypeError(
                f"Cannot initialize PasswordEncrypt from type '{type(value)}'"
            )

        # Reached only if value is None
        return None


# DATA MODELS -----------------------------------------------------------------


class Menu(Data):
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


class Orders(Data):
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


class Users(Data):
    __tablename__ = "users"
    id = Column(
        String(100),
        primary_key=True,
        nullable=False,
    )
    guest = Column(
        String(20),
        nullable=False,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    takeaway = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )
    note = Column(String(500), unique=False, nullable=True)
    orders = relationship(
        "Orders",
        back_populates="note",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<USER:{self.id}>"


class Stats(Data):
    # Primary key handled with __table_args__ bcause ON CONFLICT for composite
    # primary key is available only with __table_args__
    __tablename__ = "stats"
    __table_args__ = (
        PrimaryKeyConstraint(
            "date", "guest", name="stats_pk", sqlite_on_conflict="REPLACE"
        ),
    )
    date = Column(
        Date,
        nullable=False,
        default=datetime.utcnow(),
        server_default=func.current_timestamp(),
    )
    guest = Column(
        String(20),
        nullable=True,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    hungry_people = Column(
        Integer, nullable=False, default=0, server_default="0"
    )

    def __repr__(self):
        return f"<STAT:{self.id} - HP:{self.hungry_people} - HG:{self.hungry_guests}>"


class Flags(Data):
    __tablename__ = "flags"
    id = Column(
        String(50),
        primary_key=True,
        nullable=False,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    value = Column(Boolean, nullable=False)

    def __repr__(self):
        return f"<FLAG:{self.id} - value:{self.value}>"


# CREDENTIALS MODELS ----------------------------------------------------------
class PrivilegedUsers(Data):
    __tablename__ = "privileged_users"
    user = Column(
        String(100),
        primary_key=True,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    admin = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )

    def __repr__(self):
        return f"<AUTH_USER:{self.id}>"


class Credentials(Data):
    __tablename__ = "credentials"
    user = Column(
        String(100),
        primary_key=True,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    password_hash = Column(Password(150), unique=False, nullable=False)
    password_encrypted = Column(
        Encrypted(150),
        unique=False,
        nullable=True,
        default=None,
        server_default=None,
    )

    def __repr__(self):
        return f"<CREDENTIAL:{self.user}>"

    @validates("password_hash")
    def _validate_password(self, key, password):
        return getattr(type(self), key).type.validator(password)

    @validates("password_encrypted")
    def _validate_encrypted(self, key, password):
        return getattr(type(self), key).type.validator(password)


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


def create_exclusive_session(config: DictConfig) -> Session:
    """Database exclusive session factory function
    Database is locked until the transaction is completed (to be used to avoid
    race conditions)"""
    engine = create_engine(config)

    # Alter begin statement
    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # Emit exclusive BEGIN
        conn.exec_driver_sql("BEGIN EXCLUSIVE")

    session = Session(engine)

    return session


def create_database(config: DictConfig, add_basic_auth_users=False) -> None:
    """Database factory function"""
    # Create directory if missing
    log.debug("create 'shared_data' folder")
    pathlib.Path(config.db.shared_data_folder).mkdir(exist_ok=True)
    # Create tables
    engine = create_engine(config)
    Data.metadata.create_all(engine)

    # If requested add users for basic auth (admin and guest)
    if add_basic_auth_users:
        log.debug("add basic auth standard users")
        # If no user exist create the default admin
        session = create_session(config)
        # Check if admin exists
        if session.query(Credentials).get("admin") is None:
            # Add authorization and credentials for admin
            auth.add_privileged_user(
                user="admin",
                is_admin=True,
                config=config,
            )
            auth.add_user_hashed_password(
                user="admin",
                password="admin",
                config=config,
            )
        # Check if admin exists
        if (
            session.query(Credentials).get("guest") is None
        ) and config.panel.guest_user:
            # Add only credentials for guest (guest users are not included
            # in privileged_users table)
            auth.add_user_hashed_password(
                user="guest",
                password="guest",
                config=config,
            )


def set_flag(config: DictConfig, id: str, value: bool) -> None:
    """Set value inside flag table"""

    # Write the selected flag (it will be overwritten if exists)
    session = create_session(config)
    new_flag = Flags(id=id, value=value)
    session.add(new_flag)
    session.commit()


def get_flag(config: DictConfig, id: str) -> bool | None:
    """Get the value of a flag"""

    session = create_session(config)
    flag = session.query(Flags).get(id)
    if flag is None:
        value = None
    else:
        value = session.query(Flags).get(id).value
    return value

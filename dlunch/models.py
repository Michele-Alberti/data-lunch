"""Module with database tables definitions.

Helper classes and utility functions for data management are defined here.
"""

from datetime import datetime
import hydra
import logging
from omegaconf import DictConfig
import pathlib
import pandas as pd
from psycopg import Connection as ConnectionPostgresql
from sqlite3 import Connection as ConnectionSqlite
from sqlalchemy import (
    Column,
    PrimaryKeyConstraint,
    ForeignKey,
    Integer,
    String,
    TypeDecorator,
    Date,
    Boolean,
    Identity,
    event,
    MetaData,
    delete,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    validates,
    Session,
    DeclarativeMeta,
)
from sqlalchemy.sql import func
from sqlalchemy.sql import false as sql_false
from sqlalchemy.dialects.postgresql import insert as postgresql_upsert
import tenacity
import os

# Authentication
from . import auth

# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# DATABASE CONFIGURATIONS -----------------------------------------------------
_MODULE_TO_DIALECT_MAP: dict = {
    "psycopg2": "postgresql",
    "psycopg": "postgresql",
    "sqlite3": "sqlite",
    "sqlite": "sqlite",
}
"""Dictionary with mappings from python module name to dialect."""

# Add schema to default metadata (only if requested)
# Read directly from environment variable because config is not available here
# If config.db.schema is available SCHEMA value is overridden by the value
# set in config
SCHEMA: str = os.environ.get("DATA_LUNCH_DB_SCHEMA", None)
"""Schema name from environment (may be overridden by configuration files)."""
metadata_obj: MetaData = MetaData(schema=SCHEMA)
"""Database metadata (SQLAlchemy)."""

# Create database instance (with lazy loading)
Data: DeclarativeMeta = declarative_base(metadata=metadata_obj)
"""SQLAlchemy declarative base."""


# EVENTS ----------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Force foreign key constraints for sqlite connections.

    Args:
        dbapi_connection (Any): connection to database. Shall have a `cursor` method.
        connection_record (Any): connection record (not used).
    """
    if get_db_dialect(dbapi_connection) == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# CUSTOM COLUMNS --------------------------------------------------------------
class Password(TypeDecorator):
    """Allows storing and retrieving password hashes using PasswordHash."""

    impl: String = String
    """Base column implementation."""

    def process_bind_param(
        self, value: auth.PasswordHash | str | None, dialect
    ) -> str:
        """Ensure the value is a PasswordHash and then return its hash.

        Args:
            value (auth.PasswordHash | str): input value (plain password or hash, or `None` if empty).
            dialect (Any): dialect (not used).

        Returns:
            str: password hash.
        """
        return self._convert(value).hashed_password

    def process_result_value(
        self, value: str | None, dialect
    ) -> auth.PasswordHash | None:
        """Convert the hash to a PasswordHash, if it's non-NULL.

        Args:
            value (str | None): password hash (or `None` if empty).
            dialect (Any): dialect (not used).

        Returns:
            auth.PasswordHash | None: hashed password as object or `None` (if nothing is passed as value).
        """
        if value is not None:
            return auth.PasswordHash(value)

    def validator(
        self, password: auth.PasswordHash | str | None
    ) -> auth.PasswordHash | None:
        """Provides a validator/converter used by @validates.

        Args:
            password (auth.PasswordHash | str | None): input value (plain password or hash or `None` if empty).

        Returns:
            auth.PasswordHash | None: hashed password as object or `None` (if nothing is passed as value).
        """
        return self._convert(password)

    def _convert(
        self, value: auth.PasswordHash | str | None
    ) -> auth.PasswordHash | None:
        """Returns a PasswordHash from the given string.

        PasswordHash instances or None values will return unchanged.
        Strings will be hashed and the resulting PasswordHash returned.
        Any other input will result in a TypeError.

        Args:
            value (auth.PasswordHash | str | None): input value (plain password or hash or `None` if empty).

        Raises:
            TypeError: unknown type.

        Returns:
            auth.PasswordHash | None: hashed password as object or `None` (if nothing is passed as value).
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

    impl: String = String
    """Base column implementation."""

    def process_bind_param(
        self, value: auth.PasswordEncrypt | str | None, dialect
    ) -> str | None:
        """Ensure the value is a PasswordEncrypt and then return the encrypted password.

        Args:
            value (auth.PasswordEncrypt | str | None): input value (plain password or encrypted or `None` if empty)
            dialect (Any): dialect (not used).

        Returns:
            str | None: encrypted password or `None` if empty.
        """
        converted_value = self._convert(value)
        if converted_value:
            return converted_value.encrypted_password
        else:
            return None

    def process_result_value(
        self, value: str | None, dialect
    ) -> auth.PasswordEncrypt | None:
        """Convert the hash to a PasswordEncrypt, if it's non-NULL.

        Args:
            value (str | None): input value (plain password or encrypted or `None` if empty)
            dialect (Any): dialect (not used).

        Returns:
            auth.PasswordEncrypt | None: encrypted password as object or `None` (if nothing is passed as value).
        """
        if value is not None:
            return auth.PasswordEncrypt(value)

    def validator(
        self, password: auth.PasswordEncrypt | str | None
    ) -> auth.PasswordEncrypt | None:
        """Provides a validator/converter used by @validates.

        Args:
            password (auth.PasswordEncrypt | str | None): input value (plain password or encrypted or `None` if empty)

        Returns:
            auth.PasswordEncrypt | None: encrypted password as object or `None` (if nothing is passed as value).
        """
        return self._convert(password)

    def _convert(
        self, value: auth.PasswordEncrypt | str | None
    ) -> auth.PasswordEncrypt | None:
        """Returns a PasswordEncrypt from the given string.

        PasswordEncrypt instances or None values will return unchanged.
        Strings will be encrypted and the resulting PasswordEncrypt returned.
        Any other input will result in a TypeError.

        Args:
            value (auth.PasswordEncrypt | str | None): input value (plain password or encrypted or `None` if empty)

        Raises:
            TypeError: unknown type.

        Returns:
            auth.PasswordEncrypt | None: encrypted password as object or `None` (if nothing is passed as value).
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
    """Table with menu items."""

    __tablename__: str = "menu"
    """Name of the table."""
    id: Column = Column(
        Integer, Identity(start=1, cycle=True), primary_key=True
    )
    """Menu item ID."""
    item: Column = Column(String(250), unique=False, nullable=False)
    """Item name."""
    orders: DeclarativeMeta = relationship(
        "Orders",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    """Orders connected to each menu item."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<MENU_ITEM:{self.id} - {self.item}>"


class Orders(Data):
    """Table with items that belongs to an order."""

    __tablename__: str = "orders"
    """Name of the table."""
    id: Column = Column(
        Integer, Identity(start=1, cycle=True), primary_key=True
    )
    """Order ID."""
    user: Column = Column(
        String(100),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    """User that placed the order."""
    user_record: DeclarativeMeta = relationship(
        "Users", back_populates="orders", uselist=False
    )
    """User connected to this order."""
    menu_item_id: Column = Column(
        Integer,
        ForeignKey("menu.id", ondelete="CASCADE"),
        nullable=False,
    )
    """ID of the menu item included in the order."""
    menu_item: DeclarativeMeta = relationship("Menu", back_populates="orders")
    """Menu items connected to each order (see `menu` table)."""
    note: Column = Column(String(300), unique=False, nullable=True)
    """Note field attached to the order."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<ORDER:{self.user}, {self.menu_item.item}>"


class Users(Data):
    """Table with users that placed an order."""

    __tablename__: str = "users"
    """Name of the table."""
    id: Column = Column(
        String(100),
        primary_key=True,
        nullable=False,
    )
    """User ID."""
    guest: Column = Column(
        String(20),
        nullable=False,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    """Guest flag (true if guest)."""
    lunch_time: Column = Column(String(7), index=True, nullable=False)
    """User selected lunch time."""
    takeaway: Column = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )
    """Takeaway flag (true if takeaway)."""
    orders: DeclarativeMeta = relationship(
        "Orders",
        back_populates="user_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    """Orders connected to each user."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<USER:{self.id}>"


class Stats(Data):
    """Table with number of users that ate a lunch, grouped by guest type."""

    # Primary key handled with __table_args__ because ON CONFLICT for composite
    # primary key is available only with __table_args__
    __tablename__: str = "stats"
    """Name of the table."""
    __table_args__: tuple = (
        PrimaryKeyConstraint(
            "date", "guest", name="stats_pkey", sqlite_on_conflict="REPLACE"
        ),
    )
    """Table arguments, used to create primary key (ON CONFLICT options for composite
    primary key is available only with __table_args__)."""
    date: Column = Column(
        Date,
        nullable=False,
        server_default=func.current_date(),
    )
    """Day to which the statistics refers to."""
    guest: Column = Column(
        String(20),
        nullable=True,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    """Different kind of guests are identified by the value defined in config files
    (see config key `panel.guest_types`).
    'NotAGuest' is the value used for locals.
    """
    hungry_people: Column = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    """Number of people that ate in a certain day.
    different kind of guests are identified by the value in guest column.
    """

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<STAT:{self.id} - HP:{self.hungry_people} - HG:{self.hungry_guests}>"


class Flags(Data):
    """Table with global flags used by Data-Lunch.

    'No more orders' flag and guest override flags are stored here.
    """

    __tablename__: str = "flags"
    """Name of the table."""
    id: Column = Column(
        String(50),
        primary_key=True,
        nullable=False,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    """Flag ID (name)."""
    value: Column = Column(Boolean, nullable=False)
    """Flag value."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def clear_guest_override(self, config: DictConfig) -> int:
        """Clear 'guest_override' flags and return deleted rows

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(
                delete(self).where(self.id.like("%_guest_override"))
            )
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows (guest override) from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<FLAG:{self.id} - value:{self.value}>"


# CREDENTIALS MODELS ----------------------------------------------------------
class PrivilegedUsers(Data):
    """Table with user that have privileges (normal users and admin).

    If enabled guests are all the authenticated users that do not belong to this table
    (see config key `auth.authorize_guest_users` and `basic_auth.guest_user`)
    """

    __tablename__: str = "privileged_users"
    """Name of the table."""
    user: Column = Column(
        String(100),
        primary_key=True,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    """User name."""
    admin: Column = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )
    """Admin flag (true if admin)."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<PRIVILEGED_USER:{self.id}>"


class Credentials(Data):
    """Table with users credentials, used only if basic authentication is active."""

    __tablename__: str = "credentials"
    """Name of the table."""
    user: Column = Column(
        String(100),
        primary_key=True,
        sqlite_on_conflict_primary_key="REPLACE",
    )
    """Username."""
    password_hash: Column = Column(Password(150), unique=False, nullable=False)
    """Hashed password."""
    password_encrypted: Column = Column(
        Encrypted(150),
        unique=False,
        nullable=True,
        default=None,
        server_default=None,
    )
    """Encryped password.

    Used only if basic authentication and guest users are both active."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = create_session(config)
        with session:
            # Clean menu
            num_rows_deleted = session.execute(delete(self))
            session.commit()
            log.info(
                f"deleted {num_rows_deleted.rowcount} rows from table '{self.__tablename__}'"
            )

        return num_rows_deleted.rowcount

    @classmethod
    def read_as_df(self, config: DictConfig, **kwargs) -> pd.DataFrame:
        """Read table as pandas DataFrame.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            pd.DataFrame: dataframe with table content.
        """
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<CREDENTIAL:{self.user}>"

    @validates("password_hash")
    def _validate_password(
        self, key: str, password: str
    ) -> auth.PasswordHash | None:
        """Function that validate password input.

        It converts string to auth.PasswordHash if necessary.

        Args:
            key (str): validated attribute name.
            password (str): hashed password to be validated.

        Returns:
            auth.PasswordHash | None: validated hashed password.
        """
        return getattr(type(self), key).type.validator(password)

    @validates("password_encrypted")
    def _validate_encrypted(
        self, key: str, password: str
    ) -> auth.PasswordEncrypt | None:
        """Function that validate encrypted input.

        It converts string to auth.PasswordEncrypt if necessary.

        Args:
            key (str): validated attribute name.
            password (str): encrypted password to be validated.

        Returns:
            auth.PasswordEncrypt | None: validated encrypted password.
        """
        return getattr(type(self), key).type.validator(password)


# FUNCTIONS -------------------------------------------------------------------


def get_db_dialect(
    db_obj: Session | ConnectionSqlite | ConnectionPostgresql,
) -> str:
    """Return database type (postgresql, sqlite, etc.) based on the database object passed as input.
    If a session is passed, the database type is set based on an internal map (see `models._DBTYPE_MAP`).

    Args:
        db_obj (Session | ConnectionSqlite | ConnectionPostgresql): session or connection object.

    Raises:
        TypeError: db_obj shall be a session or a connection object.

    Returns:
        str: database dialect.
    """
    if isinstance(db_obj, Session):
        dialect = db_obj.bind.dialect.name
    elif isinstance(db_obj, ConnectionSqlite) or isinstance(
        db_obj, ConnectionPostgresql
    ):
        module = db_obj.__class__.__module__.split(".", 1)[0]
        dialect = _MODULE_TO_DIALECT_MAP[module]
    else:
        raise TypeError("db_obj should be a session or connection object")

    return dialect


def session_add_with_upsert(
    session: Session, constraint: str, new_record: Stats | Flags
) -> None:
    """Use an upsert statement for postgresql to add a new record to a table,
    a simple session add otherwise.

    Args:
        session (Session): SQLAlchemy session object.
        constraint (str): constraint used for upsert (usually the primary key)
        new_record (Stats | Flags): table resord (valid tables are `stats` or `flags`)
    """
    # Use an upsert for postgresql (for sqlite an 'on conflict replace' is set
    # on table, so session.add is fine)
    if get_db_dialect(session) == "postgresql":
        insert_statement = postgresql_upsert(new_record.__table__).values(
            {
                column.name: getattr(new_record, column.name)
                for column in new_record.__table__.c
                if getattr(new_record, column.name, None) is not None
            }
        )
        upsert_statement = insert_statement.on_conflict_do_update(
            constraint=constraint,
            set_={
                column.name: getattr(insert_statement.excluded, column.name)
                for column in insert_statement.excluded
            },
        )
        session.execute(upsert_statement)
    else:
        session.add(new_record)


def create_engine(config: DictConfig) -> Engine:
    """Factory function for SQLAlchemy engine.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        Engine: SQLAlchemy engine.
    """
    engine = hydra.utils.instantiate(config.db.engine)

    # Change schema with change_execution_options
    # If schema exist in config.db it will override the schema selected through
    # the environment variable
    if "schema" in config.db:
        engine.update_execution_options(
            schema_translate_map={SCHEMA: config.db.schema}
        )

    return engine


def create_session(config: DictConfig) -> Session:
    """Factory function for database session.

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        Session: SQLAlchemy session.
    """
    engine = create_engine(config)
    session = Session(engine)

    return session


def create_exclusive_session(config: DictConfig) -> Session:
    """Factory function for database exclusive session.
    Database is locked until the transaction is completed (to be used to avoid
    race conditions).

    Args:
        config (DictConfig): Hydra configuration dictionary.

    Returns:
        Session: SQLAlchemy exclusive session.

    Note:
        This function is not used inside Data-Lunch code.

    """
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
    """Function to create the database through SQLAlchemy models.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        add_basic_auth_users (bool, optional): set to true to add admin and guest users.
            These users are of interest only if 'basic authentication' is selected.
            Defaults to False.
    """
    # Create directory if missing
    log.debug("create 'shared_data' folder")
    pathlib.Path(config.db.shared_data_folder).mkdir(exist_ok=True)

    # In case the database is not ready use a retry mechanism
    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(OperationalError),
        wait=tenacity.wait_fixed(config.db.create_retries.wait),
        stop=(
            tenacity.stop_after_delay(config.db.create_retries.stop.delay)
            | tenacity.stop_after_attempt(
                config.db.create_retries.stop.attempts
            )
        ),
    )
    def create_database_with_retries(config: DictConfig) -> None:
        engine = create_engine(config)
        Data.metadata.create_all(engine)

    # Create tables
    log.debug(f"attempt database creation: {config.db.attempt_creation}")
    if config.db.attempt_creation:
        create_database_with_retries(config)

        # Retries stats
        log.debug(
            f"create database attempts: {create_database_with_retries.retry.statistics}"
        )

    # If requested add users for basic auth (admin and guest)
    if add_basic_auth_users:
        log.debug("add basic auth standard users")
        # If no user exist create the default admin
        session = create_session(config)

        with session:
            # Check if admin exists
            if session.get(Credentials, "admin") is None:
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
            # Check if guest exists
            if (
                session.get(Credentials, "guest") is None
            ) and config.basic_auth.guest_user:
                # Add only credentials for guest (guest users are not included
                # in privileged_users table)
                auth.add_user_hashed_password(
                    user="guest",
                    password="guest",
                    config=config,
                )


def set_flag(config: DictConfig, id: str, value: bool) -> None:
    """Set a key,value pair inside `flag` table.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        id (str): flag id (name).
        value (bool): flag value.
    """

    session = create_session(config)

    with session:
        # Write the selected flag (it will be overwritten if exists)
        new_flag = Flags(id=id, value=value)

        # Use an upsert for postgresql, a simple session add otherwise
        session_add_with_upsert(
            session=session, constraint="flags_pkey", new_record=new_flag
        )

        session.commit()


def get_flag(
    config: DictConfig, id: str, value_if_missing: bool | None = None
) -> bool | None:
    """Get the value of a flag.
    Optionally select the values to return if the flag is missing (default to None).

    Args:
        config (DictConfig): Hydra configuration dictionary.
        id (str): flag id (name).
        value_if_missing (bool | None, optional): value to return if the flag does not exist. Defaults to None.

    Returns:
        bool | None: flag value.
    """

    session = create_session(config)
    flag = session.get(Flags, id)
    if flag is None:
        value = value_if_missing
    else:
        value = flag.value
    return value

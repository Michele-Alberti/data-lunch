"""Module with database tables definitions.

Helper classes and utility functions for data management are defined here.
"""

import datetime
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
    text,
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
    if DatabaseConnector.get_db_dialect(dbapi_connection) == "sqlite":
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


class CommonTable(Data):
    """Abstract table with common methods."""

    __abstract__ = True
    """Abstract table flag."""

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows.

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """
        session = DatabaseConnector(config=config).create_session()
        with session:
            # Clean table
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
            table_name=self.__tablename__,
            con=DatabaseConnector(config=config).create_engine(),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )
        return df

    @classmethod
    def write_from_df(
        self, config: DictConfig, df: pd.DataFrame, index: bool = True
    ) -> int:
        """Write table from pandas DataFrame.

        If a record already exists in the table, it will be updated.

        Args:
            config (DictConfig): Hydra configuration dictionary.
            df (pd.DataFrame): dataframe with table content.
            index (bool): write index as a column. Use False to ignore index. Defaults to True.

        Returns:
            int: number of rows written.
        """

        session = DatabaseConnector(config=config).create_session()
        # Convert the dataframe to a dictionary of records
        drop_index = not index
        records_dict = df.reset_index(drop=drop_index).to_dict(
            orient="records"
        )

        with session:
            # Add rows
            for record in records_dict:
                # Convert the tuple to dict and expand to avoid errors
                new_record = self(**record)
                DatabaseConnector.session_add_with_upsert(
                    session=session,
                    constraint=f"{self.__tablename__}_pkey",
                    new_record=new_record,
                )

            # Commit only at the end
            session.commit()

        return len(df)


class Menu(CommonTable):
    """Table with menu items."""

    __tablename__ = "menu"
    """Name of the table."""
    id = Column(Integer, Identity(start=1, cycle=True), primary_key=True)
    """Menu item ID."""
    item = Column(String(250), unique=False, nullable=False)
    """Item name."""
    orders = relationship(
        "Orders",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    """Orders connected to each menu item."""

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<MENU_ITEM:{self.id} - {self.item}>"


class Orders(CommonTable):
    """Table with items that belongs to an order."""

    __tablename__ = "orders"
    """Name of the table."""
    id = Column(Integer, Identity(start=1, cycle=True), primary_key=True)
    """Order ID."""
    user = Column(
        String(100),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    """User that placed the order."""
    user_record = relationship("Users", back_populates="orders", uselist=False)
    """User connected to this order."""
    menu_item_id = Column(
        Integer,
        ForeignKey("menu.id", ondelete="CASCADE"),
        nullable=False,
    )
    """ID of the menu item included in the order."""
    menu_item = relationship("Menu", back_populates="orders")
    """Menu items connected to each order (see `menu` table)."""
    note = Column(String(300), unique=False, nullable=True)
    """Note field attached to the order."""

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<ORDER:{self.user}, {self.menu_item.item}>"


class Users(CommonTable):
    """Table with users that placed an order."""

    __tablename__ = "users"
    """Name of the table."""
    id = Column(
        String(100),
        primary_key=True,
        nullable=False,
    )
    """User ID."""
    guest = Column(
        String(20),
        nullable=False,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    """Guest flag (true if guest)."""
    lunch_time = Column(String(7), index=True, nullable=False)
    """User selected lunch time."""
    takeaway = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )
    """Takeaway flag (true if takeaway)."""
    orders = relationship(
        "Orders",
        back_populates="user_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    """Orders connected to each user."""

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<USER:{self.id}>"


class Stats(CommonTable):
    """Table with number of users that ate a lunch, grouped by guest type."""

    # Primary key handled with __table_args__ because ON CONFLICT for composite
    # primary key is available only with __table_args__
    __tablename__ = "stats"
    """Name of the table."""
    date = Column(
        Date,
        primary_key=True,
        nullable=False,
        server_default=func.current_date(),
    )
    """Day to which the statistics refers to."""
    guest = Column(
        String(20),
        primary_key=True,
        nullable=True,
        default="NotAGuest",
        server_default="NotAGuest",
    )
    """Different kind of guests are identified by the value defined in config files
    (see config key `panel.guest_types`).
    'NotAGuest' is the value used for locals.
    """
    hungry_people = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    """Number of people that ate in a certain day.
    different kind of guests are identified by the value in guest column.
    """

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<STAT:{self.id} - HP:{self.hungry_people} - HG:{self.hungry_guests}>"


class Birthdays(CommonTable):
    """Table with privileged users birthdays."""

    __tablename__ = "birthdays"
    """Name of the table."""
    user = Column(
        String(30),
        ForeignKey("privileged_users.user", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    """User ID (username)."""
    user_record = relationship(
        "PrivilegedUsers", back_populates="birthday_record"
    )
    """User connected to this order."""
    date = Column(
        Date,
        nullable=False,
    )
    """Users's birthday."""
    first_name = Column(
        String(30),
        nullable=False,
    )
    """User's first name."""
    last_name = Column(
        String(30),
        nullable=False,
    )
    """User's last name."""

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<STAT:{self.id} - HP:{self.hungry_people} - HG:{self.hungry_guests}>"


class Flags(CommonTable):
    """Table with global flags used by Data-Lunch.

    'No more orders' flag and guest override flags are stored here.
    """

    __tablename__ = "flags"
    """Name of the table."""
    id = Column(
        String(50),
        primary_key=True,
        nullable=False,
    )
    """Flag ID (name)."""
    value = Column(Boolean, nullable=False)
    """Flag value."""

    @classmethod
    def clear_guest_override(self, config: DictConfig) -> int:
        """Clear 'guest_override' flags and return deleted rows

        Args:
            config (DictConfig): Hydra configuration dictionary.

        Returns:
            int: deleted rows.
        """

        session = DatabaseConnector(config=config).create_session()
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

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<FLAG:{self.id} - value:{self.value}>"


# CREDENTIALS MODELS ----------------------------------------------------------
class PrivilegedUsers(CommonTable):
    """Table with user that have privileges (normal users and admin).

    If enabled guests are all the authenticated users that do not belong to this table
    (see config key `auth.authorize_guest_users` and `basic_auth.guest_user`)
    """

    __tablename__ = "privileged_users"
    """Name of the table."""
    user = Column(
        String(100),
        primary_key=True,
    )
    """User name."""
    admin = Column(
        Boolean, nullable=False, default=False, server_default=sql_false()
    )
    """Admin flag (true if admin)."""

    birthday_record = relationship(
        "Birthdays",
        uselist=False,
        back_populates="user_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<PRIVILEGED_USER:{self.id}>"


class Credentials(CommonTable):
    """Table with users credentials, used only if basic authentication is active."""

    __tablename__ = "credentials"
    """Name of the table."""
    user = Column(
        String(100),
        primary_key=True,
    )
    """Username."""
    password_hash = Column(Password(150), unique=False, nullable=False)
    """Hashed password."""
    password_encrypted = Column(
        Encrypted(150),
        unique=False,
        nullable=True,
        default=None,
        server_default=None,
    )
    """Encryped password.

    Used only if basic authentication and guest users are both active."""

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


# DATABASE CONNECTOR ----------------------------------------------------------
class DatabaseConnector:
    """Class for handling database connections and operations."""

    def __init__(self, config: DictConfig):
        self.config: DictConfig = config
        """Hydra configuration dictionary."""

    @staticmethod
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

    @staticmethod
    def session_add_with_upsert(
        session: Session, constraint: str, new_record: Stats | Flags
    ) -> None:
        """Use an upsert statement to add a new record to a table,
        for both Postgresql and SQLite databases.

        Args:
            session (Session): SQLAlchemy session object.
            constraint (str): constraint used for upsert (usually the primary key)
            new_record (Stats | Flags): table resord (valid tables are `stats` or `flags`)
        """
        # Use an upsert for postgresql (for sqlite an 'on conflict replace' is set
        # on table, so session.add is fine)
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

    @staticmethod
    def read_sql_query(session: Session, query: str) -> pd.DataFrame:
        """Read a SQL query as pandas DataFrame.

        Args:
            session (Session): SQLAlchemy session object.
            query (str): SQL query.

        Returns:
            pd.DataFrame: dataframe with query result.
        """
        results = session.execute(text(query))
        columns = results.keys()
        # Pass columns to build dataframe with correct columns names even if
        # the query returns no rows
        df = pd.DataFrame(results.all(), columns=columns)

        return df

    def create_engine(self) -> Engine:
        """Factory function for SQLAlchemy engine.

        Returns:
            Engine: SQLAlchemy engine.
        """
        engine = hydra.utils.instantiate(self.config.db.engine)

        # Change schema with change_execution_options
        # If schema exist in config.db it will override the schema selected through
        # the environment variable
        if "schema" in self.config.db:
            engine.update_execution_options(
                schema_translate_map={SCHEMA: self.config.db.schema}
            )

        return engine

    def create_session(self) -> Session:
        """Factory function for database session.

        Returns:
            Session: SQLAlchemy session.
        """
        engine = self.create_engine()
        session = Session(engine)

        return session

    def create_database(self, add_basic_auth_users=False) -> None:
        """Function to create the database through SQLAlchemy models.

        Args:
            add_basic_auth_users (bool, optional): set to true to add admin and guest users.
                These users are of interest only if 'basic authentication' is selected.
                Defaults to False.
        """
        # Create directory if missing
        log.debug("create 'shared_data' folder")
        pathlib.Path(self.config.db.shared_data_folder).mkdir(exist_ok=True)

        # In case the database is not ready use a retry mechanism
        @tenacity.retry(
            retry=tenacity.retry_if_exception_type(OperationalError),
            wait=tenacity.wait_fixed(self.config.db.create_retries.wait),
            stop=(
                tenacity.stop_after_delay(
                    self.config.db.create_retries.stop.delay
                )
                | tenacity.stop_after_attempt(
                    self.config.db.create_retries.stop.attempts
                )
            ),
        )
        def _create_database_with_retries(config: DictConfig) -> None:
            engine = self.create_engine()
            Data.metadata.create_all(engine)

        # Create tables
        log.debug(
            f"attempt database creation: {self.config.db.attempt_creation}"
        )
        if self.config.db.attempt_creation:
            _create_database_with_retries(self.config)

            # Retries stats
            log.debug(
                f"create database attempts: {_create_database_with_retries.retry.statistics}"
            )

        # If requested add users for basic auth (admin and guest)
        if add_basic_auth_users:
            log.debug("add basic auth standard users (if missing)")
            # If no user exist create the default admin
            session = self.create_session()

            with session:
                # Check if admin exists
                if session.get(Credentials, "admin") is None:
                    # Add authorization and credentials for admin
                    auth_user = auth.AuthUser(config=self.config, name="admin")
                    auth_user.add_privileged_user(is_admin=True)
                    auth_user.add_user_hashed_password(password="admin")
                    log.warning(
                        "admin user created, remember to change the default password"
                    )
                # Check if guest exists
                if (
                    session.get(Credentials, "guest") is None
                ) and self.config.basic_auth.guest_user:
                    # Add only credentials for guest (guest users are not included
                    # in privileged_users table)
                    auth_user = auth.AuthUser(config=self.config, name="guest")
                    auth_user.add_user_hashed_password(password="guest")
                    log.warning(
                        "guest user created, remember to change the default password"
                    )

    def set_flag(self, id: str, value: bool) -> None:
        """Set a key,value pair inside `flag` table.

        Args:
            id (str): flag ID (name).
            value (bool): flag value.
        """

        session = self.create_session()

        with session:
            # Write the selected flag (it will be overwritten if exists)
            new_flag = Flags(id=id, value=value)

            # Use an upsert for postgresql, a simple session add otherwise
            DatabaseConnector.session_add_with_upsert(
                session=session, constraint="flags_pkey", new_record=new_flag
            )

            session.commit()

    def get_flag(
        self, id: str, value_if_missing: bool | None = None
    ) -> bool | None:
        """Get the value of a flag.
        Optionally select the values to return if the flag is missing (default to None).

        Args:
            id (str): flag ID (name).
            value_if_missing (bool | None, optional): value to return if the flag does not exist. Defaults to None.

        Returns:
            bool | None: flag value.
        """

        session = self.create_session()

        with session:
            flag = session.get(Flags, id)
            if flag is None:
                value = value_if_missing
            else:
                value = flag.value
        return value

    def set_user_birthday(
        self,
        username: str,
        birthday_date: datetime.date,
        first_name: str,
        last_name: str,
    ) -> None:
        """Set birthday for a specific user.

        Args:
            username (str): user ID (name).
            birthday_date (bool): birthday date.
        """

        session = self.create_session()

        with session:
            # Write the selected flag (it will be overwritten if exists)
            new_birthday = Birthdays(
                user=username,
                date=birthday_date,
                first_name=first_name.lower(),
                last_name=last_name.lower(),
            )

            # Use an upsert for postgresql, a simple session add otherwise
            DatabaseConnector.session_add_with_upsert(
                session=session,
                constraint="birthdays_pkey",
                new_record=new_birthday,
            )

            session.commit()

    def get_user_birthday(self, username: str) -> Birthdays:
        """Set birthday for a specific user.

        Args:
            username (str): user ID (name).
            birthday_date (bool): birthday date.

        Returns:
            Birthdays: birthday record for the user.
        """

        session = self.create_session()

        with session:
            birthday = session.get(Birthdays, username)

        return birthday


# FUNCTIONS -------------------------------------------------------------------
# Intentionally left empty

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
from sqlalchemy.orm import declarative_base, relationship, validates, Session
from sqlalchemy.sql import func, elements
from sqlalchemy.sql import false as sql_false
from sqlalchemy.dialects.postgresql import insert as postgresql_upsert
import tenacity
import os

# Authentication
from . import auth

log = logging.getLogger(__name__)

_MODULE_TO_DIALECT_MAP = {
    "psycopg2": "postgresql",
    "psycopg": "postgresql",
    "sqlite3": "sqlite",
    "sqlite": "sqlite",
}

# Add schema to default metadata (only if requested)
# Read directly from environment variable because config is not available here
# If config.db.schema is available SCHEMA value is overridden by the value
# set in config
SCHEMA = os.environ.get("DATA_LUNCH_DB_SCHEMA", None)
metadata_obj = MetaData(schema=SCHEMA)
# Create database instance (with lazy loading)
Data = declarative_base(metadata=metadata_obj)


# EVENTS ----------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Force foreign key constraints for sqlite connections."""
    if get_db_dialect(dbapi_connection) == "sqlite":
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
    id = Column(Integer, Identity(start=1, cycle=True), primary_key=True)
    item = Column(String(250), unique=False, nullable=False)
    orders = relationship(
        "Orders",
        back_populates="menu_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self):
        return f"<MENU_ITEM:{self.id} - {self.item}>"


class Orders(Data):
    __tablename__ = "orders"
    id = Column(Integer, Identity(start=1, cycle=True), primary_key=True)
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
    note = Column(String(300), unique=False, nullable=True)

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

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

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self):
        return f"<USER:{self.id}>"


class Stats(Data):
    # Primary key handled with __table_args__ bcause ON CONFLICT for composite
    # primary key is available only with __table_args__
    __tablename__ = "stats"
    __table_args__ = (
        PrimaryKeyConstraint(
            "date", "guest", name="stats_pkey", sqlite_on_conflict="REPLACE"
        ),
    )
    date = Column(
        Date,
        nullable=False,
        server_default=func.current_date(),
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

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

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

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Clear 'guest_override' flags and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

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

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self):
        return f"<PRIVILEGED_USER:{self.id}>"


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

    @classmethod
    def clear(self, config: DictConfig) -> int:
        """Clear table and return deleted rows"""

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
        """Read table as pandas DataFrame"""
        df = pd.read_sql_table(
            self.__tablename__,
            create_engine(config=config),
            schema=config.db.get("schema", SCHEMA),
            **kwargs,
        )

        return df

    def __repr__(self):
        return f"<CREDENTIAL:{self.user}>"

    @validates("password_hash")
    def _validate_password(self, key, password):
        return getattr(type(self), key).type.validator(password)

    @validates("password_encrypted")
    def _validate_encrypted(self, key, password):
        return getattr(type(self), key).type.validator(password)


# FUNCTIONS -------------------------------------------------------------------


def get_db_dialect(
    db_obj: Session | ConnectionSqlite | ConnectionPostgresql,
) -> str:
    """Return database type (postgresql, sqlite, etc.) based on the database
    object passed as input.
    If a session is passed
    The database type is set based on an internal map (see models._DBTYPE_MAP).
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
    """Use an upsert statement for postgresql t a dd a new record to a table,
    a simple session add otherwise"""
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
    """SQLAlchemy engine factory function"""
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
    """Set value inside flag table"""

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
    """

    session = create_session(config)
    flag = session.get(Flags, id)
    if flag is None:
        value = value_if_missing
    else:
        value = flag.value
    return value

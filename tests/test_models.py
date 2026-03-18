"""Unit tests for dlunch.models module."""

import pytest
from unittest.mock import patch
from datetime import date

from dlunch.models import (
    Password,
    Encrypted,
    Menu,
    Orders,
    Users,
    Stats,
    Birthdays,
    Flags,
    PrivilegedUsers,
    Credentials,
    DatabaseConnector,
    Data,
)

import dlunch.auth as auth
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from omegaconf import OmegaConf


@pytest.fixture(scope="function")
def db_connector(test_config):
    db_connector = DatabaseConnector(config=test_config)
    db_connector.create_database()
    yield db_connector
    Data.metadata.drop_all(db_connector.create_engine())
    # Shared data folder is removed in conftest.py fixture, so no need to clean up here


class TestPasswordTypeDecorator:
    """Test Password TypeDecorator."""

    def test_process_bind_param_with_password_hash(self):
        """Test processing bind param with PasswordHash."""
        pwd_type = Password()
        ph = auth.PasswordHash("hashed_password")
        result = pwd_type.process_bind_param(ph, None)
        assert result == "hashed_password"

    def test_process_bind_param_with_string(self):
        """Test processing bind param with string."""
        pwd_type = Password()
        result = pwd_type.process_bind_param("password", None)
        assert auth.PasswordHash(result) == "password"

    def test_process_bind_param_with_none(self):
        """Test processing bind param with None."""
        pwd_type = Password()
        result = pwd_type.process_bind_param(None, None)
        assert result is None

    def test_process_result_value(self):
        """Test processing result value."""
        pwd_type = Password()
        with patch("dlunch.models.auth.PasswordHash") as mock_ph:
            pwd_type.process_result_value("hash", None)
            mock_ph.assert_called_once_with("hash")

    def test_validator(self):
        """Test validator."""
        pwd_type = Password()
        result = pwd_type.validator("password")
        assert result == "password"


class TestEncryptedTypeDecorator:
    """Test Encrypted TypeDecorator."""

    def test_process_bind_param_with_password_encrypt(self):
        """Test processing bind param with PasswordEncrypt."""
        enc_type = Encrypted()
        pe = auth.PasswordEncrypt("encrypted_password")
        result = enc_type.process_bind_param(pe, None)
        assert result == "encrypted_password"

    def test_process_bind_param_with_string(self):
        """Test processing bind param with string."""
        enc_type = Encrypted()
        result = enc_type.process_bind_param("encrypted_password", None)
        assert auth.PasswordEncrypt(result) == "encrypted_password"

    def test_process_bind_param_with_none(self):
        """Test processing bind param with None."""
        enc_type = Encrypted()
        result = enc_type.process_bind_param(None, None)
        assert result is None

    def test_process_result_value(self):
        """Test processing result value."""
        enc_type = Encrypted()
        with patch("dlunch.models.auth.PasswordEncrypt") as mock_pe:
            enc_type.process_result_value("encrypted", None)
            mock_pe.assert_called_once_with("encrypted")

    def test_validator(self):
        """Test validator."""
        enc_type = Encrypted()
        result = enc_type.validator("input")
        assert (
            result.encrypted_password
            == auth.PasswordEncrypt.from_str("input").encrypted_password
        )


class TestMenu:
    """Test Menu model."""

    def test_menu_item(self):
        """Test creating a menu item."""
        menu = Menu(item="Pizza")
        assert menu.item == "Pizza"

    def test_repr(self):
        """Test string representation."""
        menu = Menu(id=1, item="Pizza")
        assert repr(menu) == "<MENU_ITEM:1 - Pizza>"


class TestOrders:
    """Test Orders model."""

    def test_order(self):
        """Test creating an order."""
        order = Orders(user="testuser", menu_item_id=1, note="Extra cheese")
        assert order.user == "testuser"
        assert order.menu_item_id == 1
        assert order.note == "Extra cheese"

    def test_repr(self):
        """Test string representation."""
        order = Orders(user="testuser", menu_item_id=1)
        # Mock the menu_item relationship
        menu_item = Menu(id=1, item="Pizza")
        order.menu_item = menu_item
        assert repr(order) == "<ORDER:testuser, Pizza>"


class TestUsers:
    """Test Users model."""

    def test_non_guest_user(self):
        """Test creating a non-guest user."""
        user = Users(id="testuser", lunch_time="12:00", takeaway=False)
        assert user.id == "testuser"
        assert user.guest is None
        assert user.lunch_time == "12:00"
        assert user.takeaway is False

    def test_guest_user(self):
        """Test creating a guest user."""
        user = Users(
            id="testuser", guest="Guest", lunch_time="12:00", takeaway=True
        )
        assert user.id == "testuser"
        assert user.guest == "Guest"
        assert user.lunch_time == "12:00"
        assert user.takeaway is True

    def test_repr(self):
        """Test string representation."""
        user = Users(id="testuser")
        assert repr(user) == "<USER:testuser>"


class TestStats:
    """Test Stats model."""

    def test_not_guest_stats(self):
        """Test creating a stats entry for a non-guest."""
        stat = Stats(date=date.today(), guest="NotAGuest", hungry_people=5)
        assert stat.date == date.today()
        assert stat.guest == "NotAGuest"
        assert stat.hungry_people == 5

    def test_guest_stats(self):
        """Test creating a stats entry for a guest."""
        stat = Stats(date=date.today(), guest="Guest", hungry_people=3)
        assert stat.date == date.today()
        assert stat.guest == "Guest"
        assert stat.hungry_people == 3

    def test_repr(self):
        """Test string representation."""
        stat = Stats(date=date.today(), guest="NotAGuest", hungry_people=5)
        try:
            expected = f"<STAT:{date.today()} - HP:5 - G:{stat.guest}>"
        except AttributeError:
            expected = f"<STAT:{date.today()} - HP:5 - G:NotAGuest>"
        assert repr(stat) == expected


class TestBirthdays:
    """Test Birthdays model."""

    def test_birthday(self):
        """Test creating a birthday."""
        birthday = Birthdays(
            user="testuser",
            date=date(1990, 1, 1),
            first_name="Test",
            last_name="User",
        )
        assert birthday.user == "testuser"
        assert birthday.date == date(1990, 1, 1)
        assert birthday.first_name == "Test"
        assert birthday.last_name == "User"

    def test_repr(self):
        """Test string representation."""
        birthday = Birthdays(
            user="testuser",
            date=date(1990, 1, 1),
            first_name="Test",
            last_name="User",
        )
        assert repr(birthday) == "<BIRTHDAY:testuser - 1990-01-01>"


class TestFlags:
    """Test Flags model."""

    def test_true_flag(self):
        """Test creating a true flag."""
        flag = Flags(id="test_flag", value=True)
        assert flag.id == "test_flag"
        assert flag.value is True

    def test_false_flag(self):
        """Test creating a false flag."""
        flag = Flags(id="test_flag", value=False)
        assert flag.id == "test_flag"
        assert flag.value is False

    def test_repr(self):
        """Test string representation."""
        flag = Flags(id="test_flag", value=True)
        assert repr(flag) == "<FLAG:test_flag - value:True>"


class TestPrivilegedUsers:
    """Test PrivilegedUsers model."""

    def test_normal_user(self):
        """Test creating normal user."""
        user = PrivilegedUsers(user="normaluser", admin=False)
        assert user.user == "normaluser"
        assert user.admin is False

    def test_admin_user(self):
        """Test creating admin user."""
        user = PrivilegedUsers(user="adminuser", admin=True)
        assert user.user == "adminuser"
        assert user.admin is True

    def test_repr(self):
        """Test string representation."""
        user = PrivilegedUsers(user="testuser", admin=False)
        assert repr(user) == "<PRIVILEGED_USER:testuser>"


class TestCredentials:
    """Test Credentials model."""

    def test_credentials(self):
        """Test creating credentials."""
        cred = Credentials(
            user="testuser",
            password_hash="password_hash",
            password_encrypted="encrypted",
        )
        assert cred.user == "testuser"
        assert cred.password_hash == "password_hash"
        assert cred.password_encrypted == "encrypted"

    def test_repr(self):
        """Test string representation."""
        cred = Credentials(user="testuser")
        assert repr(cred) == "<CREDENTIAL:testuser>"


class TestDatabaseConnector:
    """Test DatabaseConnector class. Uses actual database operations."""

    def test_get_db_dialect_session(self, db_connector):
        """Test getting DB dialect from session."""
        session = db_connector.create_session()
        with session:
            result = DatabaseConnector.get_db_dialect(session)
        assert result == "sqlite"

    def test_create_engine(self, db_connector):
        """Test creating engine."""
        result = db_connector.create_engine()
        assert isinstance(result, Engine)

    def test_create_session(self, db_connector):
        """Test creating session."""
        session = db_connector.create_session()
        with session:
            assert isinstance(session, Session)

    def test_set_flag(self, db_connector):
        """Test setting a flag."""
        with patch(
            "dlunch.models.DatabaseConnector.session_add_with_upsert"
        ) as mock_upsert:
            db_connector.set_flag("test_flag", True)
            mock_upsert.assert_called_once()

    def test_get_flag_exists(self, db_connector):
        """Test getting an existing flag."""
        db_connector.set_flag("test_flag_true", True)
        result = db_connector.get_flag("test_flag_true")
        assert result is True
        db_connector.set_flag("test_flag_false", False)
        result = db_connector.get_flag("test_flag_false")
        assert result is False

    def test_get_flag_missing(self, db_connector):
        """Test getting a missing flag."""
        result = db_connector.get_flag(
            "test_flag_non_existent", value_if_missing="missing"
        )
        assert result == "missing"

    def test_set_user_birthday_creates_record(self, db_connector):
        """Test setting user birthday creates a record."""
        # Create a PrivilegedUsers record first (FK constraint)
        session = db_connector.create_session()
        with session:
            privileged_user = PrivilegedUsers(
                user="birthday_test_user", admin=False
            )
            session.add(privileged_user)
            session.commit()

        # Set the birthday
        test_date = date(1990, 5, 15)
        db_connector.set_user_birthday(
            "birthday_test_user", test_date, "John", "Doe"
        )

        # Verify it was created
        result = db_connector.get_user_birthday("birthday_test_user")
        assert result is not None
        assert result.user == "birthday_test_user"
        assert result.date == test_date
        assert result.first_name == "john"
        assert result.last_name == "doe"

    def test_get_user_birthday_missing_returns_none(self, db_connector):
        """Test getting a missing user birthday returns None."""
        result = db_connector.get_user_birthday("non_existent_user")
        assert result is None

    def test_delete_user_birthday_removes_record(self, db_connector):
        """Test deleting user birthday removes the record."""
        # Create a PrivilegedUsers record first (FK constraint)
        session = db_connector.create_session()
        with session:
            privileged_user = PrivilegedUsers(
                user="birthday_delete_user", admin=False
            )
            session.add(privileged_user)
            session.commit()

        # Set the birthday
        test_date = date(1985, 3, 20)
        db_connector.set_user_birthday(
            "birthday_delete_user", test_date, "Jane", "Smith"
        )

        # Delete the birthday
        deleted = db_connector.delete_user_birthday("birthday_delete_user")
        assert deleted == 1

        # Verify it was deleted
        result = db_connector.get_user_birthday("birthday_delete_user")
        assert result is None

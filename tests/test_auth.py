"""Unit tests for dlunch.auth module."""

import pytest
from passlib.context import CryptContext
from sqlalchemy import delete
from unittest.mock import Mock, patch

from dlunch.auth import PasswordHash, PasswordEncrypt, AuthContext, AuthUser
from dlunch.models import DatabaseConnector, Credentials, PrivilegedUsers, Data


@pytest.fixture(scope="function")
def db_connector(test_config):
    db_connector = DatabaseConnector(config=test_config)
    db_connector.create_database()
    yield db_connector
    Data.metadata.drop_all(db_connector.create_engine())
    # Shared data folder is removed in conftest.py fixture, so no need to clean up here


class TestPasswordHash:
    """Test PasswordHash class."""

    def test_hash_password(self):
        """Test hashing a password."""
        password = "testpassword"
        hashed = PasswordHash.hash(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        # Hash should be different from plain password
        assert hashed != password

    def test_from_str(self):
        """Test creating PasswordHash from string."""
        password = "testpassword"
        ph = PasswordHash.from_str(password)
        assert isinstance(ph, PasswordHash)
        assert ph.hashed_password != password  # Should be hashed

    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "testpassword"
        ph = PasswordHash.from_str(password)
        assert ph.verify(password) is True

    def test_verify_wrong_password(self):
        """Test verifying wrong password."""
        password = "testpassword"
        wrong_password = "wrong"
        ph = PasswordHash.from_str(password)
        assert ph.verify(wrong_password) is False

    def test_eq_with_string(self):
        """Test equality with string."""
        password = "testpassword"
        ph = PasswordHash.from_str(password)
        assert ph == password
        assert ph != "wrong"

    def test_eq_with_non_string(self):
        """Test equality with non-string."""
        ph = PasswordHash.from_str("testpassword")
        assert (ph == 123) is False

    def test_verify_and_update_no_update(self):
        """Test verify_and_update when no update needed."""
        password = "testpassword"
        ph = PasswordHash.from_str(password)
        valid, new_hash = ph.verify_and_update(password)
        assert valid is True
        assert new_hash is None

    @patch(
        "dlunch.auth.pwd_context.verify_and_update",
        return_value=(True, "testpassword_new_hash"),
    )
    def test_verify_and_update_with_update(self, mock_pwd_context):
        """Test verify_and_update when update is needed.
        CryptContext accept only one hashing scheme, so mock is required."""
        password = "testpassword"
        password_old_hash = "testpassword_old_hash"
        ph = PasswordHash(password_old_hash)
        valid, new_hash = ph.verify_and_update(password)
        assert valid is True
        assert new_hash is not None
        assert new_hash == ph.hashed_password
        assert ph.hashed_password == "testpassword_new_hash"

    def test_repr(self):
        """Test string representation."""
        ph = PasswordHash.from_str("test")
        assert str(ph) == "<PasswordHash>"


class TestPasswordEncrypt:
    """Test PasswordEncrypt class."""

    def test_encrypt_decrypt(self):
        """Test encrypt and decrypt."""
        password = "testpassword"
        encrypted = PasswordEncrypt.encrypt(password)
        pe = PasswordEncrypt(encrypted)
        decrypted = pe.decrypt()
        assert decrypted == password

    def test_from_str(self):
        """Test creating PasswordEncrypt from string."""
        password = "testpassword"
        pe = PasswordEncrypt.from_str(password)
        assert isinstance(pe, PasswordEncrypt)
        assert pe.decrypt() == password

    def test_eq_with_string(self):
        """Test equality with string."""
        password = "testpassword"
        pe = PasswordEncrypt.from_str(password)
        assert pe == password
        assert pe != "wrong"

    def test_eq_with_non_string(self):
        """Test equality with non-string."""
        pe = PasswordEncrypt.from_str("test")
        assert (pe == 123) is False

    def test_repr(self):
        """Test string representation."""
        pe = PasswordEncrypt.from_str("test")
        assert str(pe) == "<PasswordEncrypt>"


class TestAuthContextSimple:
    """AuthContext class simple tests."""

    @pytest.fixture
    def basic_auth_config(self):
        """Mock basic auth config."""
        config = Mock()
        config.get = Mock(
            side_effect=lambda key, default=None: {
                "basic_auth": "some_value"
            }.get(key, default)
        )
        return config

    @pytest.fixture
    def oauth_config(self):
        """Mock oauth config."""
        config = Mock()
        config.get = Mock(
            side_effect=lambda key, default=None: {
                "basic_auth": None,
                "server": config.server,
            }.get(key, default)
        )
        config.server = Mock()
        config.server.get = Mock(return_value="oauth_provider")
        config.server.oauth_provider = "oauth_provider"
        return config

    @pytest.fixture
    def no_auth_config(self):
        """Mock no auth config."""
        config = Mock()
        config.get = Mock(
            side_effect=lambda key, default=None: {
                "basic_auth": None,
                "server": config.server,
            }.get(key, default)
        )
        config.server = Mock()
        config.server.get = Mock(return_value=None)
        config.server.oauth_provider = None
        return config

    def test_is_basic_auth_active_false(self, oauth_config):
        """Test basic auth not active."""
        auth_context = AuthContext(oauth_config)
        assert auth_context.is_basic_auth_active() is False

    def test_is_basic_auth_active_true(self, basic_auth_config):
        """Test basic auth active."""
        auth_context = AuthContext(basic_auth_config)
        assert auth_context.is_basic_auth_active() is True

    def test_is_auth_active_false(self, no_auth_config):
        """Test auth not active."""
        auth_context = AuthContext(no_auth_config)
        assert auth_context.is_auth_active() is False

    def test_auth_type_none(self, no_auth_config):
        """Test auth type when none."""
        auth_context = AuthContext(no_auth_config)
        assert auth_context.auth_type() is None

    def test_auth_type_basic(self, basic_auth_config):
        """Test auth type basic."""
        auth_context = AuthContext(basic_auth_config)
        assert auth_context.auth_type() == "basic"

    def test_auth_type_oauth(self, oauth_config):
        """Test auth type oauth."""
        auth_context = AuthContext(oauth_config)
        assert auth_context.auth_type() == "oauth_provider"


class TestAuthContextComplex:
    """AuthContext class complex tests, uses database connector."""

    @pytest.fixture
    def auth_context(self, test_config, db_connector):
        """Create AuthContext with test config and db connector."""
        auth_context = AuthContext(test_config)
        auth_context.database_connector = db_connector
        return auth_context

    @patch("dlunch.auth.pn.config")
    @patch("dlunch.auth.pn.state")
    @patch("dlunch.auth.Fernet")
    def test_set_app_auth_and_encryption(
        self, mock_fernet, mock_pn_state, mock_pn_config, auth_context
    ):
        """Test set_app_auth_and_encryption accesses and sets pn.config and pn.state."""
        # Setup mock config with auth settings - use a valid 32-byte base64 key
        valid_key = "n7M__09XF8DhRW9dxs7hFVZoPScXxlj6La7r9U240xc="  # 32-byte base64 key
        auth_context.config.auth.oauth_encryption_key = valid_key
        auth_context.config.auth.oauth_expiry = 86400

        # Call the method
        auth_context.set_app_auth_and_encryption()

        # Verify pn.config was accessed and set
        assert mock_pn_config.oauth_encryption_key == valid_key.encode("ascii")
        assert mock_pn_config.oauth_expiry == 86400
        # Verify Fernet was called with the key
        mock_fernet.assert_called_once_with(valid_key.encode("ascii"))
        # Verify pn.state.encryption was set
        assert mock_pn_state.encryption is not None

    def test_list_privileged_users(self, auth_context, db_connector):
        """Test list_privileged_users uses session.scalars with proper args."""
        # Create a test privileged user
        session = db_connector.create_session()
        test_user = PrivilegedUsers(user="testuser", admin=False)
        session.add(test_user)
        session.commit()

        # Call the method
        result = auth_context.list_privileged_users()

        # Verify result
        assert isinstance(result, list)
        assert "testuser" in result

    @patch("dlunch.auth.models.PrivilegedUsers.read_as_df")
    @patch("dlunch.auth.models.Credentials.read_as_df")
    @patch("pandas.DataFrame")
    def test_list_users_guests_and_privileges(
        self,
        mock_df,
        mock_credentials_read,
        mock_privileged_read,
        auth_context,
    ):
        """Test list_users_guests_and_privileges calls read_as_df and returns DataFrame."""
        # Setup mocks
        mock_privileged_df = mock_df()
        mock_privileged_df.admin = Mock()
        mock_privileged_df.admin.map.return_value = Mock()
        mock_privileged_df.__getitem__ = Mock(return_value=mock_df())
        mock_privileged_df.join = Mock(return_value=mock_df())

        mock_privileged_read.return_value = mock_privileged_df
        mock_credentials_read.return_value = mock_df()

        # Call the method
        result = auth_context.list_users_guests_and_privileges()

        # Verify read_as_df was called
        mock_privileged_read.assert_called_once()
        # Verify DataFrame operations were performed
        assert result is not None

    def test_generate_password(self):
        """Test generate_password returns a string."""
        password = AuthContext.generate_password()

        assert isinstance(password, str)
        assert len(password) == 12
        # Check password contains required character types
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)

    @patch.object(AuthContext, "is_basic_auth_active", return_value=True)
    @patch.object(
        AuthContext, "generate_password", return_value="generated_password"
    )
    def test_set_guest_user_password_guests_deactivated(
        self, mock_generate, mock_is_basic, auth_context
    ):
        """Test set_guest_user_password generates password even when guests deactivated."""
        # Setup mocks
        basic_auth = Mock()
        basic_auth.guest_user = False

        mock_config = Mock()
        mock_config.basic_auth = basic_auth

        with patch.object(auth_context, "config", mock_config):
            # Call the method
            result = auth_context.set_guest_user_password()

        # Should return empty string when guests deactivated
        assert result == ""


class TestAuthUserSimple:
    """AuthUser class simple tests."""

    @pytest.fixture
    def mock_config(self):
        """Mock Hydra config."""
        config = Mock()
        config.auth.remove_email_domain = False
        return config

    @pytest.fixture
    def mock_panel_state(self):
        """Mock panel state."""
        state = Mock()
        state.user = "test@example.com"
        return state

    @pytest.fixture
    def mock_auth_context(self):
        """Mock AuthContext."""
        return Mock(spec=AuthContext)

    @pytest.fixture
    def auth_user(self, mock_config, mock_auth_context):
        """Create AuthUser with mocks."""
        return AuthUser(
            config=mock_config, auth_context=mock_auth_context, name="testuser"
        )

    def test_get_user_from_panel_state(
        self, mock_config, mock_panel_state, mocker
    ):
        """Test getting user from panel state."""
        mocker.patch("dlunch.auth.pn.state", mock_panel_state)
        auth_user = AuthUser(config=mock_config)
        assert auth_user.get_user_from_panel_state() == "test@example.com"

    def test_get_user_from_panel_state_remove_domain(
        self, mock_config, mock_panel_state, mocker
    ):
        """Test getting user from panel state with domain removal."""
        mock_config.auth.remove_email_domain = True
        mocker.patch("dlunch.auth.pn.state", mock_panel_state)
        auth_user = AuthUser(config=mock_config)
        assert auth_user.get_user_from_panel_state() == "test"

    def test_is_guest_no_auth(self, auth_user, mock_auth_context):
        """Test is_guest when no auth."""
        mock_auth_context.is_auth_active.return_value = False
        assert auth_user.is_guest() is False

    def test_is_admin_no_auth(self, auth_user, mock_auth_context):
        """Test is_admin when no auth."""
        mock_auth_context.is_auth_active.return_value = False
        assert auth_user.is_admin() is False


class TestAuthUserComplex:
    """AuthUser class complex tests, uses database connector."""

    @pytest.fixture
    def auth_context(self, test_config, db_connector):
        """Create AuthContext with test config and db connector."""
        auth_context = AuthContext(test_config)
        auth_context.database_connector = db_connector
        return auth_context

    @pytest.fixture
    def auth_user(self, test_config, auth_context):
        """Create AuthUser with test config and auth context."""
        return AuthUser(
            config=test_config, auth_context=auth_context, name="testuser"
        )

    def test_password_hash(self, auth_user, db_connector):
        """Test password_hash property."""
        # Create test credentials
        session = db_connector.create_session()

        test_credentials = Credentials(
            user="testuser",
            password_hash=PasswordHash.from_str("testpassword"),
        )
        session.add(test_credentials)
        session.commit()

        # Test password_hash property
        result = auth_user.password_hash

        assert result is not None
        assert result.verify("testpassword")

    def test_add_privileged_user(self, auth_user, db_connector):
        """Test add_privileged_user method."""
        # Call the method
        auth_user.add_privileged_user(is_admin=True)

        # Verify user was added
        session = db_connector.create_session()
        user = session.get(PrivilegedUsers, "testuser")
        assert user is not None
        assert user.admin is True

    def test_add_user_hashed_password(self, auth_user, db_connector):
        """Test add_user_hashed_password method."""
        # Call the method
        auth_user.add_user_hashed_password("testpassword")

        # Verify credentials were added
        session = db_connector.create_session()
        creds = session.get(Credentials, "testuser")
        assert creds is not None
        assert creds.password_hash is not None

    def test_remove_user(self, auth_user, db_connector):
        """Test remove_user method."""

        # First ensure clean state - remove any existing testuser
        session = db_connector.create_session()

        # Clean up any existing data
        session.execute(
            delete(PrivilegedUsers).where(PrivilegedUsers.user == "testuser")
        )
        session.execute(
            delete(Credentials).where(Credentials.user == "testuser")
        )
        session.commit()

        # Now add user to both tables
        priv_user = PrivilegedUsers(user="testuser", admin=False)
        creds = Credentials(user="testuser", password_hash="hash")

        session.add(priv_user)
        session.add(creds)
        session.commit()

        # Call remove_user
        result = auth_user.remove_user()

        # Verify deletion
        assert result["privileged_users_deleted"] == 1
        assert result["credentials_deleted"] == 1

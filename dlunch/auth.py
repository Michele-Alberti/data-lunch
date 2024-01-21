import logging
import json
from omegaconf import DictConfig
from omegaconf.errors import ConfigAttributeError
from passlib.context import CryptContext
from passlib.utils import saslprep
import pandas as pd
import panel as pn
from panel.auth import OAuthProvider
from panel.util import base64url_encode
import re
import secrets
import string
from sqlalchemy.sql import true as sql_true
from sqlalchemy import select, delete
import tornado
from tornado.web import RequestHandler

# Database
from . import models


# LOGGER ----------------------------------------------------------------------
log = logging.getLogger(__name__)


# CONTEXT ---------------------------------------------------------------------
# Create a crypt context for the app
pwd_context = CryptContext(
    # Replace this list with the hash(es) you wish to support.
    # this example sets pbkdf2_sha256 as the default,
    # add other ashes after pbkdf2_sha256 for additional support on
    # legacy hashes.
    schemes=["pbkdf2_sha256"],
    # Automatically mark all but first hasher in list as deprecated.
    # (this will be the default in Passlib 2.0)
    deprecated="auto",
    # Optionally, set the number of rounds that should be used.
    # Appropriate values may vary for different schemes,
    # and the amount of time you wish it to take.
    # Leaving this alone is usually safe, and will use passlib's defaults.
    ## pbkdf2_sha256__rounds = 29000,
)

# PROPERTIES ------------------------------------------------------------------
# Intentionally left void

# CLASSES ---------------------------------------------------------------------


class DataLunchProvider(OAuthProvider):
    def __init__(self, config, login_template=None, logout_template=None):
        # Set Hydra config info
        self.config = config

        super().__init__(
            login_template=login_template, logout_template=logout_template
        )

    @property
    def login_url(self):
        return "/login"

    @property
    def login_handler(self):
        # Set basic template
        DataLunchLoginHandler._login_template = self._login_template
        # Set Hydra config info
        DataLunchLoginHandler.config = self.config

        return DataLunchLoginHandler


# optional login page for login_url
class DataLunchLoginHandler(RequestHandler):
    def get(self):
        try:
            errormessage = self.get_argument("error")
        except Exception:
            errormessage = ""
        html = self._login_template.render(errormessage=errormessage)
        self.write(html)

    def check_permission(self, user, password):
        password_hash = get_hash_from_user(user, self.config)
        if password_hash == password:
            # Check if hash needs update
            valid, new_hash = password_hash.verify_and_update(password)
            if valid and new_hash:
                # Update to new hash
                add_user_hashed_password(user, password, config=self.config)
            # Return the OK value
            return True
        # Return the NOT OK value
        return False

    def post(self):
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        auth = self.check_permission(username, password)
        if auth:
            self.set_current_user(username)
            self.redirect("/")
        else:
            error_msg = "?error=" + tornado.escape.url_escape(
                "Login incorrect"
            )
            self.redirect("/login" + error_msg)

    def set_current_user(self, user):
        if not user:
            self.clear_cookie("user")
            return
        self.set_secure_cookie(
            "user",
            user,
            expires_days=pn.config.oauth_expiry,
            **self.config.auth.cookie_kwargs,
        )
        id_token = base64url_encode(json.dumps({"user": user}))
        if pn.state.encryption:
            id_token = pn.state.encryption.encrypt(id_token.encode("utf-8"))
        self.set_secure_cookie(
            "id_token",
            id_token,
            expires_days=pn.config.oauth_expiry,
            **self.config.auth.cookie_kwargs,
        )


class PasswordHash:
    def __init__(self, hashed_password: str):
        # Consistency checks
        assert (
            len(hashed_password) <= 150
        ), "hash should have less than 150 chars."
        # Attributes
        self.hashed_password = hashed_password

    def __eq__(self, candidate: str):
        """Hashes the candidate string and compares it to the stored hash."""
        # If string check hash, otherwise return False
        if isinstance(candidate, str):
            # Replace hashed_password if the algorithm changes
            valid = self.verify(candidate)
        else:
            valid = False

        return valid

    def __repr__(self):
        """Simple object representation."""
        return f"<{type(self).__name__}>"

    def verify(self, password: str) -> bool:
        """Check a password against its hash and return True if check passes,
        False otherwise."""
        valid = pwd_context.verify(saslprep(password), self.hashed_password)

        return valid

    def verify_and_update(self, password: str) -> bool:
        """Check a password against its hash and return True if check passes,
        False otherwise. Return also a new hash if the original hashing  method
        is superseeded"""
        valid, new_hash = pwd_context.verify_and_update(
            saslprep(password), self.hashed_password
        )
        if valid and new_hash:
            self.hashed_password = new_hash

        return valid, new_hash

    @staticmethod
    def hash(password: str):
        """Return hash of the given password."""
        return pwd_context.hash(saslprep(password))

    @classmethod
    def from_str(cls, password: str):
        """Creates a PasswordHash from the given string."""
        return cls(cls.hash(password))


class PasswordEncrypt:
    def __init__(self, encrypted_password: str):
        # Consistency checks
        assert (
            len(encrypted_password) <= 150
        ), "encrypted string should have less than 150 chars."
        # Attributes
        self.encrypted_password = encrypted_password

    def __eq__(self, candidate: str):
        """Decrypt the candidate string and compares it to the stored encrypted value."""
        # If string check hash, otherwise return False
        if isinstance(candidate, str):
            # Replace hashed_password if the algorithm changes
            valid = self.decrypt() == candidate
        else:
            valid = False

        return valid

    def __repr__(self):
        """Simple object representation."""
        return f"<{type(self).__name__}>"

    @staticmethod
    def encrypt(password: str):
        """Return encrypted password."""
        if pn.state.encryption:
            encrypted_password = pn.state.encryption.encrypt(
                password.encode("utf-8")
            ).decode("utf-8")
        else:
            encrypted_password = password
        return encrypted_password

    def decrypt(self):
        """Return decrypted password."""
        if pn.state.encryption:
            password = pn.state.encryption.decrypt(
                self.encrypted_password.encode("utf-8")
            ).decode("utf-8")
        else:
            password = self.encrypted_password
        return password

    @classmethod
    def from_str(cls, password: str):
        """Creates a PasswordHash from the given string."""
        return cls(cls.encrypt(password))


# FUNCTIONS -------------------------------------------------------------------


def pn_user(config: DictConfig) -> str:
    """Return the user from Panel state object.
    If remove_email_domain is True, remove the domain from the user."""
    # Store user
    user = pn.state.user

    if user:
        # Check if username is an email
        if re.fullmatch(r"[^@]+@[^@]+\.[^@]+", user):
            # Remove domain from username
            if config.auth.remove_email_domain:
                user = user.split("@")[0]

    return user


def is_basic_auth_active(config: DictConfig) -> bool:
    """Check config object and return true if basic authentication is active.
    Return false otherwise."""

    # Check if a valid auth key exists
    auth_provider = config.get("basic_auth", None)

    return auth_provider is not None


def is_auth_active(config: DictConfig) -> bool:
    """Check config object and return true if basic authentication or OAuth is active.
    Return false otherwise."""

    # Check if a valid auth key exists
    auth_provider = is_basic_auth_active(config=config)
    oauth_provider = config.server.get("oauth_provider", None)

    return auth_provider or oauth_provider


def authorize(
    config: DictConfig,
    user_info: dict,
    target_path: str,
    authorize_guest_users=False,
) -> bool:
    """Authorization callback, read config, user info and target path.
    Return True (authorized) or False (not authorized) by checking current user
    and target path"""

    # If authorization is not active authorize every user
    if not is_auth_active(config=config):
        return True

    # Set current user from panel state
    current_user = pn_user(config)
    privileged_users = list_users(config=config)
    log.debug(f"target path: {target_path}")
    # If user is not authenticated block it
    if not current_user:
        return False
    # All privileged users can reach backend (but the backend will have
    # controls only for admins)
    if current_user in privileged_users:
        return True
    # If the target is the mainpage always authorized (if authenticated)
    if authorize_guest_users and (target_path == "/"):
        return True

    # In all other cases, don't authorize and logout
    pn.state.location.pathname.split("/")[0] + "/logout"
    return False


def set_app_auth_and_encryption(config: DictConfig) -> None:
    try:
        if config.auth.oauth_encryption_key:
            try:
                from cryptography.fernet import Fernet
            except ImportError:
                raise ImportError(
                    "Using Data-Lunch authentication requires the "
                    "cryptography library. Install it with `pip install "
                    "cryptography` or `conda install cryptography`."
                )
            pn.config.oauth_encryption_key = (
                config.auth.oauth_encryption_key.encode("ascii")
            )
            pn.state.encryption = Fernet(pn.config.oauth_encryption_key)
    except ConfigAttributeError:
        log.warning(
            "missing authentication encryption key, generate a key with the `panel oauth-secret` CLI command and then provide it to hydra using the DATA_LUNCH_OAUTH_ENC_KEY environment variable"
        )
    # Cookie expiry date
    try:
        if config.auth.oauth_expiry:
            pn.config.oauth_expiry = config.auth.oauth_expiry
    except ConfigAttributeError:
        log.warning(
            "missing explicit authentication expiry date for cookies, defaults to 1 day"
        )


def get_hash_from_user(user: str, config: DictConfig) -> PasswordHash | None:
    # Create session
    session = models.create_session(config)
    # Load user from database
    with session:
        user_credential = session.get(models.Credentials, user)

    # Get the hashed password
    if user_credential:
        hash = user_credential.password_hash or None
    else:
        hash = None

    return hash


def add_privileged_user(user: str, is_admin: bool, config: DictConfig) -> None:
    """Add user id to 'privileged_users' table.
    The table is used by all authentication method to understand which users are
    privileged and which ones are guests."""
    # Create session
    session = models.create_session(config)
    # New credentials
    new_privileged_user = models.PrivilegedUsers(user=user, admin=is_admin)

    # Update credentials
    # Use an upsert for postgresql, a simple session add otherwise
    models.session_add_with_upsert(
        session=session,
        constraint="privileged_users_pkey",
        new_record=new_privileged_user,
    )
    session.commit()


def add_user_hashed_password(
    user: str, password: str, config: DictConfig
) -> None:
    """Add user credentials to 'credentials' table.
    Used only by basic authentication"""
    # Create session
    session = models.create_session(config)
    # New credentials
    # For the user named "guest" add also the encrypted password so that panel
    # can show the decrypted guest password to logged users
    # Can't use is_guest to determine the user that need encription, because
    # only the user named guest is shown in the guest user password widget
    if user == "guest":
        new_user_credential = models.Credentials(
            user=user, password_hash=password, password_encrypted=password
        )
    else:
        new_user_credential = models.Credentials(
            user=user, password_hash=password
        )

    # Update credentials
    # Use an upsert for postgresql, a simple session add otherwise
    models.session_add_with_upsert(
        session=session,
        constraint="credentials_pkey",
        new_record=new_user_credential,
    )
    session.commit()


def remove_user(user: str, config: DictConfig) -> None:
    # Create session
    session = models.create_session(config)

    with session:
        # Delete user from privileged_users table
        privileged_users_deleted = session.execute(
            delete(models.PrivilegedUsers).where(
                models.PrivilegedUsers.user == user
            )
        )
        session.commit()

        # Delete user from credentials table
        credentials_deleted = session.execute(
            delete(models.Credentials).where(models.Credentials.user == user)
        )
        session.commit()

    return {
        "privileged_users_deleted": privileged_users_deleted.rowcount,
        "credentials_deleted": credentials_deleted.rowcount,
    }


def list_users(config: DictConfig) -> list[str]:
    """List only privileged users.
    Returns a list."""
    # Create session
    session = models.create_session(config)

    with session:
        privileged_users = session.scalars(
            select(models.PrivilegedUsers)
        ).all()

    # Return users
    users_list = [u.user for u in privileged_users]
    users_list.sort()

    return users_list


def list_users_guests_and_privileges(config: DictConfig) -> pd.DataFrame:
    """Join privileged users' table and credentials tables to list users,
    admins and guests.
    Returns a dataframe."""

    # Query tables required to understand users and guests
    df_privileged_users = models.PrivilegedUsers.read_as_df(
        config=config,
        index_col="user",
    )
    df_credentials = models.Credentials.read_as_df(
        config=config,
        index_col="user",
    )
    # Change admin column to privileges (used after join)
    df_privileged_users["group"] = df_privileged_users.admin.map(
        {True: "admin", False: "user"}
    )
    df_user_guests_privileges = df_privileged_users.join(
        df_credentials, how="outer"
    )[["group"]]
    df_user_guests_privileges = df_user_guests_privileges.fillna("guest")

    return df_user_guests_privileges


def is_guest(
    user: str, config: DictConfig, allow_override: bool = True
) -> bool:
    """Check if a user is a guest by checking if it is listed inside the 'privileged_users' table
    The guest override chached value (per-user) can force the function to always return True.
    If allow_override is set to False the guest override value is ignored."""

    # If authorization is not active always return false (user is not guest)
    if not is_auth_active(config=config):
        return False

    # Load guest override from flag table (if the button is pressed its value
    # is True). If not available use False.
    guest_override = models.get_flag(
        config=config,
        id=f"{pn_user(config)}_guest_override",
        value_if_missing=False,
    )

    # If guest override is active always return true (user act like guest)
    if guest_override and allow_override:
        return True

    # Otherwise check if user is not included in privileged users
    privileged_users = list_users(config)

    is_guest = user not in privileged_users

    return is_guest


def is_admin(user: str, config: DictConfig) -> bool:
    """Check if a user is an dmin by checking the 'privileged_users' table"""

    # If authorization is not active always return false (ther is no admin)
    if not is_auth_active(config=config):
        return False

    # Create session
    session = models.create_session(config)

    with session:
        admin_users = session.scalars(
            select(models.PrivilegedUsers).where(
                models.PrivilegedUsers.admin == sql_true()
            )
        ).all()
    admin_list = [u.user for u in admin_users]

    is_admin = user in admin_list

    return is_admin


def open_backend() -> None:
    # Edit pathname to open backend
    pn.state.location.pathname = (
        pn.state.location.pathname.split("/")[0] + "/backend"
    )
    pn.state.location.reload = True


def force_logout() -> None:
    # Edit pathname to force logout
    pn.state.location.pathname = (
        pn.state.location.pathname.split("/")[0] + "/logout"
    )
    pn.state.location.reload = True


def generate_password(
    alphabet: str | None = None,
    special_chars: str | None = "",
    length: int = 12,
) -> str:
    # If alphabet is not avilable use a default one
    if alphabet is None:
        alphabet = string.ascii_letters + string.digits + special_chars
    # Infinite loop for finding a valid password
    while True:
        password = "".join(secrets.choice(alphabet) for i in range(length))
        # Create special chars condition only if special chars is non-empty
        if special_chars:
            special_chars_condition = any(c in special_chars for c in password)
        else:
            special_chars_condition = True
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and special_chars_condition
        ):
            break

    return password

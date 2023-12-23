import logging
import json
from omegaconf import DictConfig
from omegaconf.errors import ConfigAttributeError
from passlib.context import CryptContext
from passlib.utils import saslprep
import pathlib
import panel as pn
from panel.auth import OAuthProvider
from panel.util import base64url_encode
from panel.io.resources import BASIC_LOGIN_TEMPLATE, _env
import secrets
import string
from sqlalchemy.ext.mutable import Mutable
import tornado
from tornado.web import RequestHandler, decode_signed_value

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
credentials_filename = (
    pathlib.Path(__file__).parent.parent / "shared_data" / "credentials.json"
)
guest_password_filename = (
    pathlib.Path(__file__).parent.parent
    / "shared_data"
    / "guest_password.pickle"
)

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
    user_credential = session.query(models.Credentials).get(user)

    # Get the hashed password
    if user_credential:
        hash = user_credential.password_hash or None
    else:
        hash = None

    return hash


def add_user_hashed_password(
    user: str, password: str, config: DictConfig
) -> None:
    # Create session
    session = models.create_session(config)
    # New credentials
    # For guest user add also the encrypted password so that panle can show
    # the decrypted guest password to logged users
    if user == "guest":
        new_user_credential = models.Credentials(
            user=user, password_hash=password, password_encrypted=password
        )
    else:
        new_user_credential = models.Credentials(
            user=user, password_hash=password
        )

    # Update credentials
    session.add(new_user_credential)
    session.commit()


def remove_user(user: str, config: DictConfig) -> None:
    # Create session
    session = models.create_session(config)

    # Delete user
    users_deleted = (
        session.query(models.Credentials)
        .filter(models.Credentials.user == user)
        .delete()
    )
    session.commit()

    return users_deleted


def list_users(config: DictConfig) -> list[str]:
    # Create session
    session = models.create_session(config)

    credentials = session.query(models.Credentials).all()

    # Return keys (users)
    users_list = [c.user for c in credentials]
    users_list.sort()

    return users_list


def get_username_from_cookie(cookie_secret: str) -> str:
    secure_cookie = pn.state.curdoc.session_context.request.cookies["user"]
    user = decode_signed_value(cookie_secret, "user", secure_cookie).decode(
        "utf-8"
    )

    return user


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

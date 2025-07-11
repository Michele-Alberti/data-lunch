"""Module with classes and functions used for authentication and password handling."""

# The __future__ import is necessary to avoid circular imports, it make all
# the type hints in this file to be interpreted as strings
from __future__ import annotations

import logging
import json
import pandas as pd
import panel as pn
import re
import secrets
import string
import tornado

from cryptography.fernet import Fernet, InvalidToken
from omegaconf import DictConfig
from omegaconf.errors import ConfigAttributeError
from panel.auth import OAuthProvider
from panel.util import base64url_encode
from passlib.context import CryptContext
from passlib.utils import saslprep
from sqlalchemy.sql import true as sql_true
from sqlalchemy import select, delete
from time import sleep
from tornado.web import RequestHandler
from typing import Self, TYPE_CHECKING

# Package imports
from . import models

# Import used only for type checking, that have problems with circular imports
# TYPE_CHECKING is False at runtime (thus the import is not executed)
if TYPE_CHECKING:
    from . import gui


# LOGGER ----------------------------------------------------------------------
log: logging.Logger = logging.getLogger(__name__)
"""Module logger."""


# CONTEXT ---------------------------------------------------------------------
# Create a crypt context for the app
pwd_context: CryptContext = CryptContext(
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
"""Crypt context with configurations for passlib (selected algorithm, etc.)."""

# PROPERTIES ------------------------------------------------------------------
# Intentionally left void

# CLASSES ---------------------------------------------------------------------


# optional login page for login_url
class DataLunchLoginHandler(RequestHandler):
    """Custom Panel login Handler.

    This class run the user authentication process for Data-Lunch when basic authentication
    is selected in configuration options.

    It is responsible of rendering the login page, validate the user (and update its
    password hash if the hashing protocol is superseeded) and set the current user once validated.
    """

    def get(self) -> None:
        """Render the login template."""
        try:
            errormessage = self.get_argument("error")
        except Exception:
            errormessage = ""
        html = self._login_template.render(errormessage=errormessage)
        self.write(html)

    def _validate(self, user: str, password: str) -> bool:
        """Validate user.

        Automatically update the password hash if it was generated by an old hashing protocol.

        Args:
            user (str): username.
            password (str): password (not hashed).

        Returns:
            bool: user authentication flag (`True` if authenticated)
        """
        auth_user = AuthUser(config=self.config, name=user)
        password_hash = auth_user.password_hash
        # If password_hash is None the user does not exist
        # If password_hash is not None check if the password matches
        # the stored hash
        if password_hash is not None:
            if password_hash == password:
                # Check if hash needs update
                valid, new_hash = password_hash.verify_and_update(password)
                if valid and new_hash:
                    # Update to new hash
                    auth_user.add_user_hashed_password(password)
                # Return the OK value
                return True
        # Return the NOT OK value
        return False

    def post(self) -> None:
        """Validate user and set the current user if valid."""
        username = self.get_argument("username", "")
        password = self.get_argument("password", "")
        auth = self._validate(username, password)
        if auth:
            self.set_current_user(username)
            next_url = pn.state.base_url
            self.redirect(next_url)
        else:
            error_msg = "?error=" + tornado.escape.url_escape(
                "Invalid username or password!"
            )
            self.redirect("/login" + error_msg)

    def set_current_user(self, user: str):
        """Set secure cookie for the selected user.

        Args:
            user (str): username.
        """
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


class DataLunchProvider(OAuthProvider):
    """Custom Panel auth provider.

    It's a simple login page with a form that interacts with authentication tables.

    It is used only if basic authentication is selected in Data-Lunch configuration options.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        login_template (str | None, optional): path to login template. Defaults to None.
        logout_template (str | None, optional): path to logout template. Defaults to None.
    """

    def __init__(
        self,
        config: DictConfig,
        login_template: str | None = None,
        logout_template: str | None = None,
    ) -> None:
        # Set Hydra config info
        self.config: DictConfig = config
        """Hydra configuration dictionary."""

        super().__init__(
            login_template=login_template, logout_template=logout_template
        )

    @property
    def login_url(self) -> str:
        """Login url (`/login`)."""
        return "/login"

    @property
    def login_handler(self) -> DataLunchLoginHandler:
        """Data-Lunch custom login handler."""
        # Set basic template
        DataLunchLoginHandler._login_template = self._login_template
        # Set Hydra config info
        DataLunchLoginHandler.config = self.config

        return DataLunchLoginHandler


class PasswordHash:
    """Class that store the hashed value of a password.

    The password hash may be passed to instantiate the new object.
    If the hash is not aviailable use the class method
    `PasswordHash.from_str` to create an istance with the string properly
    hashed.

    Args:
        hashed_password (str): password hash.
    """

    def __init__(self, hashed_password: str) -> None:
        # Consistency checks
        assert (
            len(hashed_password) <= 150
        ), "hash should have less than 150 chars."
        # Attributes
        self.hashed_password: str = hashed_password
        """Password hash."""

    def __eq__(self, candidate: str) -> bool:
        """Hashes the candidate string and compares it to the stored hash.

        Args:
            candidate (str): candidate string.

        Returns:
            bool: `True` if equal.
        """
        # If string check hash, otherwise return False
        if isinstance(candidate, str):
            # Replace hashed_password if the algorithm changes
            valid = self.verify(candidate)
        else:
            valid = False

        return valid

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<{type(self).__name__}>"

    def verify(self, password: str) -> bool:
        """Check a password against its hash and return `True` if check passes,
        `False` otherwise.

        Args:
            password (str): plain password (not hashed).

        Returns:
            bool: `True` if password and hash match.
        """
        valid = pwd_context.verify(saslprep(password), self.hashed_password)

        return valid

    def verify_and_update(self, password: str) -> tuple[bool, str | None]:
        """Check a password against its hash and return `True` if check passes,
        `False` otherwise. Return also a new hash if the original hashing  method
        is superseeded

        Args:
            password (str): plain password (not hashed).

        Returns:
            tuple[bool, str | None]: return a tuple with two elements (valid, new_hash).
                valid: `True` if password and hash match.
                new_hash: new hash to replace the one generated with an old algorithm.
        """
        valid, new_hash = pwd_context.verify_and_update(
            saslprep(password), self.hashed_password
        )
        if valid and new_hash:
            self.hashed_password = new_hash

        return valid, new_hash

    @staticmethod
    def hash(password: str) -> str:
        """Return hash of the given password.

        Args:
            password (str): plain password (not hashed).

        Returns:
            str: hashed password.
        """
        return pwd_context.hash(saslprep(password))

    @classmethod
    def from_str(cls, password: str) -> Self:
        """Creates a PasswordHash from the given string.

        Args:
            password (str): plain password (not hashed).

        Returns:
            PasswordHash: new class instance with hashed value already stored.
        """
        return cls(cls.hash(password))


class PasswordEncrypt:
    """Class that store the encrypted value of a password.

    The encryption is based on Panel encryption system.

    The class has methods to encrypt and decrypt a string.

    The encrypted password may be passed to instantiate the new object.
    If the encrypted password is not aviailable use the class method
    `PasswordEncrypt.from_str` to create an istance with the string properly
    encrypted.

    Args:
        encrypted_password (str): encrypted password.
    """

    def __init__(self, encrypted_password: str) -> None:
        # Consistency checks
        assert (
            len(encrypted_password) <= 150
        ), "encrypted string should have less than 150 chars."
        # Attributes
        self.encrypted_password: str = encrypted_password
        """Encrypted password."""

    def __eq__(self, candidate: str) -> bool:
        """Decrypt the candidate string and compares it to the stored encrypted value.

        Args:
            candidate (str): candidate string.

        Returns:
            bool: `True` if equal.
        """
        # If string check hash, otherwise return False
        if isinstance(candidate, str):
            # Replace hashed_password if the algorithm changes
            valid = self.decrypt() == candidate
        else:
            valid = False

        return valid

    def __repr__(self) -> str:
        """Simple object representation.

        Returns:
            str: string representation.
        """
        return f"<{type(self).__name__}>"

    @staticmethod
    def encrypt(password: str) -> str:
        """Return encrypted password.

        Args:
            password (str): plain password (not encrypted).

        Returns:
            str: encrypted password.
        """
        if pn.state.encryption:
            encrypted_password = pn.state.encryption.encrypt(
                password.encode("utf-8")
            ).decode("utf-8")
        else:
            encrypted_password = password
        return encrypted_password

    def decrypt(self) -> str:
        """Return decrypted password.

        Returns:
            str: plain password (not encrypted).
        """
        if pn.state.encryption:
            password = pn.state.encryption.decrypt(
                self.encrypted_password.encode("utf-8")
            ).decode("utf-8")
        else:
            password = self.encrypted_password
        return password

    @classmethod
    def from_str(cls, password: str) -> Self:
        """Creates a PasswordEncrypt from the given string.

        Args:
            password (str): plain password (not encrypted).

        Returns:
            PasswordEncrypt: new class instance with encrypted value already stored.
        """
        return cls(cls.encrypt(password))


class AuthContext:
    """Class to handle authentication context and related operations.

    Args:
        config (DictConfig): Hydra configuration dictionary.
    """

    def __init__(self, config: DictConfig) -> None:
        self.config = config
        """Hydra configuration dictionary."""
        self.database_connector: models.DatabaseConnector = (
            models.DatabaseConnector(config=config)
        )
        """Object that handles database connection and operations"""

    def is_basic_auth_active(self) -> bool:
        """Check configuration object and return `True` if basic authentication is active.
        Return `False` otherwise.

        Returns:
            bool: `True` if basic authentication is active, `False` otherwise.
        """
        # Check if a valid basic_auth key exists
        auth_provider = self.config.get("basic_auth", None)
        return auth_provider is not None

    def is_auth_active(self) -> bool:
        """Check configuration object and return `True` if basic authentication or OAuth is active.
        Return `False` otherwise.

        Returns:
            bool: `True` if authentication (basic or OAuth) is active, `False` otherwise.
        """
        # Check if a valid oauth key exists
        auth_provider = self.is_basic_auth_active()
        oauth_provider = (
            self.config.server.get("oauth_provider", None) is not None
        )
        return auth_provider or oauth_provider

    def auth_type(self) -> str | None:
        """Check configuration object and return authentication type.

        Returns:
            str | None: authentication type. None if no authentication is active.
        """
        if self.is_basic_auth_active():
            auth_type = "basic"
        elif self.config.server.get("oauth_provider", None) is not None:
            auth_type = self.config.server.oauth_provider
        else:
            auth_type = None

        return auth_type

    def set_app_auth_and_encryption(self) -> None:
        """Setup Panel authorization and encryption.

        Namely:
            - Encryption key
            - Cookie expiry date

        Raises:
            ImportError: missing library (cryptography).
        """
        # Encryption key
        try:
            if self.config.auth.oauth_encryption_key:
                pn.config.oauth_encryption_key = (
                    self.config.auth.oauth_encryption_key.encode("ascii")
                )
                pn.state.encryption = Fernet(pn.config.oauth_encryption_key)
        except ConfigAttributeError:
            log.warning(
                "missing authentication encryption key, generate a key with the `panel oauth-secret` CLI command and then provide it to hydra using the DATA_LUNCH_OAUTH_ENC_KEY environment variable"
            )
        # Cookie expiry date
        try:
            if self.config.auth.oauth_expiry:
                pn.config.oauth_expiry = self.config.auth.oauth_expiry
        except ConfigAttributeError:
            log.warning(
                "missing explicit authentication expiry date for cookies, defaults to 1 day"
            )

    def list_privileged_users(self) -> list[str]:
        """List only privileged users (from `privileged_users` table).

        Returns:
            list[str]: list of usernames.
        """
        session = self.database_connector.create_session()

        with session:
            privileged_users = session.scalars(
                select(models.PrivilegedUsers)
            ).all()

        # Return users
        users_list = [u.user for u in privileged_users]
        users_list.sort()

        return users_list

    def list_users_guests_and_privileges(self) -> pd.DataFrame:
        """Join `privileged_users` and `credentials` tables to list normal users,
        admins and guests.

        Returns a dataframe.

        Returns:
            pd.DataFrame: dataframe with users and privileges.
        """

        # Query tables required to understand users and guests
        df_privileged_users = models.PrivilegedUsers.read_as_df(
            config=self.config,
            index_col="user",
        )
        # Leave credentials table empty if basic auth is not active
        if self.is_basic_auth_active():
            df_credentials = models.Credentials.read_as_df(
                config=self.config,
                index_col="user",
            )
        else:
            df_credentials = pd.DataFrame()

        # Change admin column to privileges (used after join)
        df_privileged_users["group"] = df_privileged_users.admin.map(
            {True: "admin", False: "user"}
        )
        df_user_guests_privileges = df_privileged_users.join(
            df_credentials, how="outer"
        )[["group"]]
        df_user_guests_privileges = df_user_guests_privileges.fillna("guest")

        return df_user_guests_privileges

    @staticmethod
    def generate_password(
        alphabet: str | None = None,
        special_chars: str | None = "",
        length: int = 12,
    ) -> str:
        """Generate a random password.

        Args:
            alphabet (str | None, optional): list of characters to use as alphabet to generate the password.
                Defaults to None.
            special_chars (str | None, optional): special characters to include inside the password string.
                Defaults to "".
            length (int, optional): length of the random password.
                Defaults to 12.

        Returns:
            str: random password.
        """
        # If alphabet is not avilable use a default one
        if alphabet is None:
            alphabet = string.ascii_letters + string.digits + special_chars
        # Infinite loop for finding a valid password
        while True:
            password = "".join(secrets.choice(alphabet) for i in range(length))
            # Create special chars condition only if special chars is non-empty
            if special_chars:
                special_chars_condition = any(
                    c in special_chars for c in password
                )
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

    def set_guest_user_password(self) -> str:
        """If guest user is active return a password, otherwise return an empty string.

        This function always returns an empty string if basic authentication is not active.

        Guest user and basic authentication are handled through configuration files.

        If the flag `reset_guest_user_password` is set to `True` the password is created
        and uploaded to database. Otherwise the existing password is queried from database
        `credentials` table.

        Returns:
            str: guest user password or empty string if basic authentication is not active.
        """
        # Check if basic auth is active
        if self.is_basic_auth_active():
            # If active basic_auth.guest_user is true if guest user is active
            is_guest_user_active = self.config.basic_auth.guest_user
            log.debug(f"guest user flag is {is_guest_user_active}")
        else:
            # Otherwise the guest user feature is not applicable
            is_guest_user_active = False
            log.debug("guest user not applicable")

        # Set the guest password variable
        if is_guest_user_active:
            # If flag for resetting the password does not exist use the default
            # value
            if (
                self.database_connector.get_flag(
                    id="reset_guest_user_password"
                )
                is None
            ):
                self.database_connector.set_flag(
                    id="reset_guest_user_password",
                    value=self.config.basic_auth.default_reset_guest_user_password_flag,
                )
            # Generate a random password only if requested (check on flag)
            # otherwise load from database
            if self.database_connector.get_flag(
                id="reset_guest_user_password"
            ):
                # Turn off reset user password (in order to reset it only once)
                # This statement also acquire a lock on database (so it is
                # called first)
                self.database_connector.set_flag(
                    id="reset_guest_user_password",
                    value=False,
                )
                # Create password
                guest_password = self.generate_password(
                    special_chars=self.config.basic_auth.psw_special_chars,
                    length=self.config.basic_auth.generated_psw_length,
                )
                # Add hashed password to database
                AuthUser(
                    config=self.config, auth_context=self, name="guest"
                ).add_user_hashed_password(guest_password)
            else:
                # Load from database
                session = self.database_connector.create_session()
                with session:
                    try:
                        guest_password = session.get(
                            models.Credentials, "guest"
                        ).password_encrypted.decrypt()
                    except InvalidToken:
                        # Notify exception and suggest to reset guest user password
                        guest_password = ""
                        log.warning(
                            "Unable to decrypt 'guest' user password because an invalid token has been detected: reset password from backend"
                        )
                        pn.state.notifications.warning(
                            "Unable to decrypt 'guest' user password<br>Invalid token detected: reset password from backend",
                            duration=self.config.panel.notifications.duration,
                        )
        else:
            guest_password = ""

        return guest_password

    def submit_password(self, gi: gui.GraphicInterface) -> bool:
        """Same as backend_submit_password with an additional check on old password.

        Args:
            gi (gui.GraphicInterface): graphic interface object (used to interact with Panel widgets).

        Returns:
            bool: true if successful, false otherwise.
        """
        # Get authenticated user from Panel state
        auth_user = AuthUser(config=self.config, auth_context=self)
        # Get username, updated updated at each key press
        old_password_key_press = gi.password_widget._widgets[
            "old_password"
        ].value_input
        # Check if old password is correct
        if auth_user.password_hash == old_password_key_press:
            # Then run the same checks used for backend
            return self.backend_submit_password(
                gi=gi, user=auth_user.name, logout_on_success=True
            )
        else:
            pn.state.notifications.error(
                "Incorrect old password!",
                duration=self.config.panel.notifications.duration,
            )
        return False

    def backend_submit_password(
        self,
        gi: gui.GraphicInterface | gui.BackendInterface,
        user: str = None,
        user_is_guest: bool | None = None,
        user_is_admin: bool | None = None,
        logout_on_success: bool = False,
    ) -> bool:
        """Submit password to database from backend but used also from frontend as part of `submit_password` function.

        Args:
            gi (gui.GraphicInterface | gui.BackendInterface): graphic interface object (used to interact with Panel widgets).
            user (str, optional): username. Defaults to None.
            user_is_guest (bool | None, optional): guest flag (true if guest). Defaults to None.
            user_is_admin (bool | None, optional): admin flag (true if admin). Defaults to None.
            logout_on_success (bool, optional): set to true to force logout once the new password is set. Defaults to False.

        Returns:
            bool: true if successful, false otherwise.
        """
        # Check if user is passed, otherwise check if backend widget
        # (password_widget.object.user) is available
        if not user:
            username = gi.password_widget._widgets["user"].value_input
        else:
            username = user
        # Get all passwords, updated at each key press
        new_password_key_press = gi.password_widget._widgets[
            "new_password"
        ].value_input
        repeat_new_password_key_press = gi.password_widget._widgets[
            "repeat_new_password"
        ].value_input
        # Check if new password match repeat password
        if username:
            if new_password_key_press == repeat_new_password_key_press:
                # Check if new password is valid with regex
                if re.fullmatch(
                    self.config.basic_auth.psw_regex,
                    new_password_key_press,
                ):
                    auth_user = AuthUser(
                        config=self.config, auth_context=self, name=username
                    )
                    # If is_guest and is_admin are None (not passed) use the ones
                    # already set for the user
                    if user_is_guest is None:
                        user_is_guest = auth_user.is_guest(
                            allow_override=False
                        )
                    if user_is_admin is None:
                        user_is_admin = auth_user.is_admin()
                    # First check user existence in 'privileged_users' and
                    # 'credentials' tables.
                    session = self.database_connector.create_session()
                    with session:
                        # Check if user exists in privileged_users table
                        user_exists = (
                            session.get(models.PrivilegedUsers, username)
                            is not None
                        )
                        # Check if user exists in credentials table
                        credentials_exists = (
                            session.get(models.Credentials, username)
                            is not None
                        )
                    if (user_exists) or (credentials_exists):
                        pn.state.notifications.success(
                            f"Users<br>'{username}'<br>already exists<br>data will be overwritten",
                            duration=self.config.panel.notifications.duration,
                        )
                    else:
                        pn.state.notifications.warning(
                            f"Creating new user<br>'{username}' does not exist",
                            duration=self.config.panel.notifications.duration,
                        )
                    # Add a privileged users only if guest option is not active
                    if not user_is_guest:
                        auth_user.add_privileged_user(is_admin=user_is_admin)
                    # Green light: update the password!
                    auth_user.add_user_hashed_password(
                        password=new_password_key_press
                    )

                    # Logout if requested
                    if logout_on_success:
                        pn.state.notifications.success(
                            "Password updated<br>Logging out",
                            duration=self.config.panel.notifications.duration,
                        )
                        sleep(4)
                        gi.force_logout()
                    else:
                        pn.state.notifications.success(
                            "Password updated",
                            duration=self.config.panel.notifications.duration,
                        )
                    return True
                else:
                    pn.state.notifications.error(
                        "Password requirements not satisfied<br>Check again!",
                        duration=self.config.panel.notifications.duration,
                    )
            else:
                pn.state.notifications.error(
                    "Passwords are different!",
                    duration=self.config.panel.notifications.duration,
                )
        else:
            pn.state.notifications.error(
                "Missing user!",
                duration=self.config.panel.notifications.duration,
            )

        return False


class AuthUser:
    """Class to handle user authentication and management.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        name (str | None, optional): username. Defaults to None.
        auth_context (AuthContext | None, optional): authentication context. Defaults to None.
    """

    def __init__(
        self,
        config: DictConfig,
        name: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> None:
        self.config = config
        self.auth_context = auth_context or AuthContext(config)
        # Take username from Panel state if not provided
        self.name = name or self.get_user_from_panel_state()

    def get_user_from_panel_state(self) -> str:
        """Return the user from Panel state object.

        If `config.auth.remove_email_domain` is `True`, remove the email domain from username.

        Returns:
            str: username.
        """
        user = pn.state.user
        # Check if username is an email
        if user and re.fullmatch(r"[^@]+@[^@]+\.[^@]+", user):
            # Remove domain from username
            if self.config.auth.remove_email_domain:
                user = user.split("@")[0]
        return user

    def is_guest(self, allow_override: bool = True) -> bool:
        """Check if a user is a guest by checking if it is listed inside the `privileged_users` table.

        Args:
            allow_override (bool, optional): override enablement flag. Defaults to True.

        Returns:
            bool: guest flag. `True` if the user is a guest.
        """
        # If authorization is not active always return false (user is not guest)
        if not self.auth_context.is_auth_active():
            return False

        # Load guest override from flag table (if the button is pressed its value
        # is True). If not available use False.
        guest_override = self.auth_context.database_connector.get_flag(
            id=f"{self.name}_guest_override",
            value_if_missing=False,
        )

        # If guest override is active always return true (user act like guest)
        if guest_override and allow_override:
            return True

        # Otherwise check if user is not included in privileged users
        privileged_users = self.auth_context.list_privileged_users()

        return self.name not in privileged_users

    def is_admin(self) -> bool:
        """Check if a user is an admin by checking the `privileged_users` table.

        Returns:
            bool: admin flag. `True` if the user is an admin.
        """
        # If authorization is not active always return false (ther is no admin)
        if not self.auth_context.is_auth_active():
            return False
        session = self.auth_context.database_connector.create_session()
        with session:
            admin_users = session.scalars(
                select(models.PrivilegedUsers).where(
                    models.PrivilegedUsers.admin == sql_true()
                )
            ).all()

        return self.name in [u.user for u in admin_users]

    @property
    def password_hash(self) -> PasswordHash | None:
        """Query the database to retrieve the hashed password for the user.

        Returns:
            PasswordHash | None: returns password object if the user exists, `None` otherwise.
        """
        session = self.auth_context.database_connector.create_session()
        # Get the hashed password if user exists
        with session:
            user_credential = session.get(models.Credentials, self.name)
        return user_credential.password_hash if user_credential else None

    def add_privileged_user(self, is_admin: bool) -> None:
        """Add user id to `privileged_users` table.

        Args:
            is_admin (bool): admin flag.
        """
        session = self.auth_context.database_connector.create_session()
        # New credentials
        new_privileged_user = models.PrivilegedUsers(
            user=self.name, admin=is_admin
        )
        # Update credentials
        # Use an upsert for postgresql, a simple session add otherwise
        models.DatabaseConnector.session_add_with_upsert(
            session=session,
            constraint="privileged_users_pkey",
            new_record=new_privileged_user,
        )
        session.commit()

    def add_user_hashed_password(self, password: str) -> None:
        """Add user credentials to `credentials` table.

        Args:
            password (str): plain password (not hashed).
        """
        session = self.auth_context.database_connector.create_session()
        # New credentials
        # For the user named "guest" add also the encrypted password so that panel
        # can show the decrypted guest password to logged users
        # Can't use is_guest to determine the user that need encription, because
        # only the user named guest is shown in the guest user password widget
        if self.name == "guest":
            new_user_credential = models.Credentials(
                user=self.name,
                password_hash=password,
                password_encrypted=password,
            )
        else:
            new_user_credential = models.Credentials(
                user=self.name, password_hash=password
            )
        # Update credentials
        # Use an upsert for postgresql, a simple session add otherwise
        models.DatabaseConnector.session_add_with_upsert(
            session=session,
            constraint="credentials_pkey",
            new_record=new_user_credential,
        )
        session.commit()

    def remove_user(self) -> dict:
        """Remove user from the database.

        Returns:
            dict: dictionary with `privileged_users_deleted` and `credentials_deleted`
                with deleted rows from each table.
        """
        session = self.auth_context.database_connector.create_session()

        with session:
            # Delete user from privileged_users table
            privileged_users_deleted = session.execute(
                delete(models.PrivilegedUsers).where(
                    models.PrivilegedUsers.user == self.name
                )
            )
            session.commit()

            # Delete user from credentials table
            credentials_deleted = session.execute(
                delete(models.Credentials).where(
                    models.Credentials.user == self.name
                )
            )
            session.commit()

        return {
            "privileged_users_deleted": privileged_users_deleted.rowcount,
            "credentials_deleted": credentials_deleted.rowcount,
        }


class AuthCallback:
    """Class to handle authorization callback.

    Args:
        config (DictConfig): Hydra configuration dictionary.
        authorize_guest_users (bool, optional): Set to `True` to enable the main page to guest users.
            Defaults to `False`.
    """

    def __init__(
        self, config: DictConfig, authorize_guest_users: bool = False
    ) -> None:
        self.config = config
        self.authorize_guest_users = authorize_guest_users

    def authorize(self, user_info: dict, target_path: str) -> bool:
        """Authorization callback: read config, user info and the target path of the
        requested resource.

        Return `True` (authorized) or `False` (not authorized) by checking current user
        and target path.

        Args:
            user_info (dict): dictionary with user info passed by Panel to the authorization handle.
            target_path (str): path of the requested resource.

        Returns:
            bool: authorization flag. `True` if authorized.
        """
        # Set authenticated user from panel state (authentication context is
        # instantiated automatically)
        auth_user = AuthUser(config=self.config)
        # If authorization is not active authorize every user
        if not auth_user.auth_context.is_auth_active():
            return True
        # Get privileged users
        privileged_users = auth_user.auth_context.list_privileged_users()
        log.debug(f"target path: {target_path}")
        # If user is not authenticated block it
        if not auth_user.name:
            log.debug("user not authenticated")
            return False
        # All privileged users can reach backend (but the backend will have
        # controls only for admins)
        if auth_user.name in privileged_users:
            return True
        # If the target is the mainpage always authorized (if authenticated)
        if self.authorize_guest_users and (target_path == "/"):
            return True

        # In all other cases, don't authorize and logout
        log.debug("not authorized")
        pn.state.location.pathname.split("/")[0] + "/logout"
        return False


# FUNCTIONS -------------------------------------------------------------------
# Intentionally left void

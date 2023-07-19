import logging
import json
from passlib.context import CryptContext
import pathlib
import tornado
from tornado.web import RequestHandler, decode_signed_value
import panel as pn
from panel.auth import OAuthProvider
from panel.util import base64url_encode
from panel.io.resources import BASIC_LOGIN_TEMPLATE, _env
import secrets
import string

# Graphic interface
from . import gui


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
credentials_filename = pathlib.Path(__file__).parent / "credentials.json"

# CLASSES ---------------------------------------------------------------------


class DataLunchProvider(OAuthProvider):
    def __init__(self, basic_login_template=None):
        if basic_login_template is None:
            self._basic_login_template = BASIC_LOGIN_TEMPLATE
        else:
            with open(basic_login_template) as f:
                self._basic_login_template = _env.from_string(f.read())
        super().__init__()

    @property
    def login_url(self):
        return "/login"

    @property
    def login_handler(self):
        DataLunchLoginHandler._basic_login_template = (
            self._basic_login_template
        )
        return DataLunchLoginHandler


# optional login page for login_url
class DataLunchLoginHandler(RequestHandler):
    def get(self):
        try:
            errormessage = self.get_argument("error")
        except Exception:
            errormessage = ""
        html = self._basic_login_template.render(errormessage=errormessage)
        self.write(html)

    def check_permission(self, user, password):
        if verify_and_update_hash(user, password):
            return True
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
            "user", user, expires_days=pn.config.oauth_expiry
        )
        id_token = base64url_encode(json.dumps({"user": user}))
        if pn.state.encryption:
            id_token = pn.state.encryption.encrypt(id_token.encode("utf-8"))
        self.set_secure_cookie(
            "id_token", id_token, expires_days=pn.config.oauth_expiry
        )


# FUNCTIONS -------------------------------------------------------------------


def get_hash_from_user(user: str) -> str:
    # Load user from json file
    try:
        with open(credentials_filename) as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError as e:
        log.error("missing credential file")
        raise e

    # Search for user
    hash = credentials.get(user, None)

    return hash


def add_user_hashed_password(user: str, password: str) -> None:
    # Load user from json file
    try:
        with open(credentials_filename) as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError:
        log.warning("missing credential file, writing a new one")
        credentials = {}

    # Update credentials
    credentials.update({user: pwd_context.hash(password)})

    # Save to json file
    with open(credentials_filename, "w") as credentials_file:
        json.dump(credentials, credentials_file, indent=4)


def replace_user_hash(user: str, new_hash: str) -> None:
    # Load user from json file
    try:
        with open(credentials_filename) as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError as e:
        log.error("missing credential file")
        raise e

    # Update credentials
    credentials.update({user: new_hash})

    # Save to json file
    with open(credentials_filename, "w") as credentials_file:
        json.dump(credentials, credentials_file, indent=4)


def verify_and_update_hash(user: str, password: str) -> bool | None:
    """check if a password inputed by the user matches its hash given a user,
    and a password

    Return true if a valid match is found, None otherwise
    """
    hash = get_hash_from_user(user)

    if hash:
        valid, new_hash = pwd_context.verify_and_update(password, hash)
        if valid:
            if new_hash:
                replace_user_hash(user, new_hash)
            return True
        else:
            return None
    else:
        return None


def remove_user(user: str) -> None:
    # Load user from json file
    try:
        with open(credentials_filename) as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError as e:
        log.error("missing credential file")
        raise e

    # Update credentials
    credentials.pop(user)

    # Save to json file
    with open(credentials_filename, "w") as credentials_file:
        json.dump(credentials, credentials_file, indent=4)


def list_users() -> list[str]:
    # Load user from json file
    try:
        with open(credentials_filename) as credentials_file:
            credentials = json.load(credentials_file)
    except FileNotFoundError as e:
        log.error("missing credential file")
        raise e

    # Return keys (users)
    users_list = [key for key in credentials]
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
        password = "".join(secrets.choice(alphabet) for i in range(length + 1))
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

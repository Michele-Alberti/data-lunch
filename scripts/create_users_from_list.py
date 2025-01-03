#! python
# This script create users credentials starting from an excel file downloaded
# from GCP storage.
# For each new user that is created a email is sent to an address based on the
# user name.
# A random password is created for each user inside the Excel file
# (that contains also the email address for each user).
# The other script arguments are passed to Hydra.

# Email client
import ssl
import smtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import os
import pathlib

# Password
import dlunch.auth as auth
from dlunch.cloud import download_from_gcloud_as_bytes
import pandas as pd
from hydra import compose, initialize
import sys

# USER NAMES ------------------------------------------------------------------
# Command arguments (for Hydra)
hydra_args = sys.argv[1:]

# global initialization
initialize(
    config_path="../dlunch/conf",
    job_name="script_create_users_from_list",
    version_base="1.3",
)
config = compose(config_name="config", overrides=hydra_args)

# Download file with users names
new_users_names = download_from_gcloud_as_bytes(
    source_blob_name="new_users_names.xlsx",
    bucket_name=config.db.ext_storage_upload.bucket_name,
    project=config.db.ext_storage_upload.project,
)

# Build dataframe
new_users_names_df = pd.read_excel(
    new_users_names, header=None, names=["name", "email"]
)
if new_users_names_df.empty:
    raise (ValueError("the dataframe with usernames and emails is empty"))

# Jinja template
template_folder = pathlib.Path(__file__).parent / "ip_email"
env = Environment(
    loader=FileSystemLoader(template_folder.resolve()),
    autoescape=select_autoescape(["html", "xml"]),
)
template = env.get_template("user_credentials.html")

# Logo image
image_filename = template_folder / "pizza_and_slice.png"
attachment_cid = make_msgid()

# EMAIL CLIENT ----------------------------------------------------------------
# Environment variables
mail_username = os.environ["MAIL_USER"]
mail_password = os.environ["MAIL_APP_PASSWORD"]
mail_sender = os.environ["MAIL_USER"]
domain = os.environ["DOMAIN"]

# Message
send_from = mail_sender

# MIME
for user in new_users_names_df.itertuples():
    # Generate a random password
    auth_user = auth.AuthUser(config=config, name=user.name)
    password = auth_user.auth_context.generate_password(
        special_chars=config.basic_auth.psw_special_chars
    )
    # Add hashed password to credentials file
    auth_user.add_user_hashed_password(password=password)

    # Send email to user: recipient (built from username)
    send_to = user.email
    # Body
    body = template.render(
        username=user.name,
        password=password,
        attachment_cid=attachment_cid[1:-1],
    )

    # Build MIME object (for each user)
    msg = EmailMessage()
    msg["From"] = send_from
    msg["To"] = send_to
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = "[Data-Lunch] Login Credentials"

    # Attach
    msg.set_content(body, "html")
    with open(image_filename, "rb") as image_file:
        msg.add_related(image_file.read(), "image", "jpeg", cid=attachment_cid)

    # Server
    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.login(mail_username, mail_password)
        smtp.send_message(msg)

    print(f"email for user '{user.name}' sent to {user.email}")

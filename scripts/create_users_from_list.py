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
import html
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import os

# Password
import data_lunch_app.auth as auth
from data_lunch_app.cloud import download_from_gcloud_as_bytes
import pandas as pd
from hydra import compose, initialize
import sys

# USER NAMES ------------------------------------------------------------------
# Command arguments (for Hydra)
hydra_args = sys.argv[1:]

# global initialization
initialize(
    config_path="../data_lunch_app/conf",
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
    # Build MIME object (for each user)
    msg = MIMEMultipart()
    msg["From"] = send_from
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = "[Data-Lunch] Login Credentials"

    # Generate a random password
    password = auth.generate_password(
        special_chars=config.panel.psw_special_chars
    )
    # Add hashed password to credentials file
    auth.add_user_hashed_password(user.name, password)
    # Send email to user
    # Recipient (built from username)
    send_to = user.email
    msg["To"] = send_to
    # Body
    body = f"""\
            <html>
            <body>
                <h3>Data-Lunch Login Credentials</h3>
                <p>
                    <strong>USERNAME:</strong> {user.name}<br>
                    <strong>PASSWORD:</strong> {html.escape(password)}<br>
                </p>
            </body>
            </html>
            """

    msg.attach(MIMEText(body, "html"))
    # Server
    context = ssl.create_default_context()
    smtp = smtplib.SMTP("smtp.gmail.com", 587)
    smtp.ehlo()
    smtp.starttls(context=context)
    smtp.login(mail_username, mail_password)
    smtp.sendmail(send_from, send_to.split(","), msg.as_string())
    smtp.quit()

    print(f"email for user '{user.name}' sent to {user.email}")

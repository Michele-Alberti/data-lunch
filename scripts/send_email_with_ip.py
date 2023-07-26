#! python
# This script send an email to recipients by using the selected account.
# The email contains the external IP and the domain of the virtual machine.
# In addition the password for the guest user is set and sent with
# the same email.

from jinja2 import Environment, FileSystemLoader, select_autoescape
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import requests
import os
import pathlib

# Environment variables
username = os.environ["MAIL_USER"]
password = os.environ["MAIL_APP_PASSWORD"]
recipients = os.environ["MAIL_RECIPIENTS"]
mail_user = os.environ["MAIL_USER"]
domain = os.environ["DOMAIN"]

# External IP
metadata_server = "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip"
metadata_flavor = {"Metadata-Flavor": "Google"}
external_ip = requests.get(metadata_server, headers=metadata_flavor).text

# Jinja template
template_folder = pathlib.Path(__file__).parent / "ip_email"
env = Environment(
    loader=FileSystemLoader(template_folder.resolve()),
    autoescape=select_autoescape(["html", "xml"]),
)
template = env.get_template("ip_email.html")

# Logo image
image_filename = template_folder / "pizza_and_slice.png"
attachment_cid = make_msgid()

# Message
send_from = mail_user
send_to = recipients
body = template.render(
    domain=domain,
    external_ip=external_ip,
    attachment_cid=attachment_cid[1:-1],
)

# MIME
msg = EmailMessage()
msg["From"] = send_from
msg["To"] = send_to
msg["Date"] = formatdate(localtime=True)
msg["Subject"] = "[Data-Lunch] VM instance IP"

# Attach
msg.set_content(body, "html")
with open(image_filename, "rb") as image_file:
    msg.add_related(image_file.read(), "image", "jpeg", cid=attachment_cid)

# Server
context = ssl.create_default_context()
with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
    smtp.ehlo()
    smtp.starttls(context=context)
    smtp.login(username, password)
    smtp.send_message(msg)

print("email with external IP sent")

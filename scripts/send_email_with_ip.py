#! python
# This script send an email to recipients by using the selected account.
# The email contains the external IP and the domain of the virtual machine.
# In addition the password for the guest user is set and sent with
# the same email.
# The other script arguments are passed to Hydra.

import data_lunch_app.auth as auth
from hydra import compose, initialize
import html
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import requests
import os
import sys

# Command arguments (for Hydra)
hydra_args = sys.argv[1:]

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

# Guest user password
# Global initialization (Hydra)
initialize(
    config_path="../data_lunch_app/conf",
    job_name="script_send_email_with_ip",
    version_base="1.3",
)
config = compose(config_name="config", overrides=hydra_args)
# Generate a random password
guest_password = auth.generate_password(
    special_chars=config.panel.psw_special_chars
)
# Add hashed password to credentials file
auth.add_user_hashed_password("guest", guest_password)

# Message
send_from = mail_user
send_to = recipients
body = f"""\
<html>
  <body>
    <p>Buongiorno, Data-Lunch è online!<br><br>
       Per accedere all'app da rete aziendale (o con connessione VPN) clicca
       <strong><a href="https://{external_ip}">qui</a></strong>.<br>
       <em>Nella schermata di avvertimento "la connessione non è privata" (con il browser Edge)
       clicca su "Avanzate" e poi "Procedi su...".</em><br><br>
       Se non sei collegato alla rete aziendale, oppure se sei su rete mobile,
       puoi collegarti a
       <strong><a href="https://{domain}/">{domain}</a></strong>.
    </p>
    <p>
      Per l'accesso con l'utente <i>guest</i> usare la password:<br><br>
      {html.escape(guest_password)}
    </p>
  </body>
</html>
"""

# MIME
msg = MIMEMultipart()
msg["From"] = send_from
msg["To"] = send_to
msg["Date"] = formatdate(localtime=True)
msg["Subject"] = "[Data-Lunch] VM instance IP"
msg.attach(MIMEText(body, "html"))

# Server
context = ssl.create_default_context()
smtp = smtplib.SMTP("smtp.gmail.com", 587)
smtp.ehlo()
smtp.starttls(context=context)
smtp.login(username, password)
smtp.sendmail(send_from, send_to.split(","), msg.as_string())
smtp.quit()

print("email with external IP sent")

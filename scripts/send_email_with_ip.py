#! python

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import requests
import time
import os

# Environment variables
username = os.environ["MAIL_USER"]
password = os.environ["MAIL_APP_PASSWORD"]
recipients = os.environ["MAIL_RECIPIENTS"]

# External IP
metadata_server = "http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip"
metadata_flavor = {"Metadata-Flavor": "Google"}
external_ip = requests.get(metadata_server, headers=metadata_flavor).text

# Message
timestr = time.strftime("(%Y-%m-%d)")
send_from = "data.lunch.email@gmail.com"
send_to = recipients
body = f"""\
<html>
  <body>
    <p>Buongiorno, Data-Lunch è online!<br><br>
       Per accedere all'app da rete Edison (o con connessione VPN) clicca
       <strong><a href="https://{external_ip}">qui</a></strong>.<br>
       <em>Nella schermata di avvertimento "la connessione non è privata" (con il browser Edge)
       clicca su "Avanzate" e poi "Procedi su...".</em><br><br>
       Se non sei collegato alla rete Edison, oppure se sei su rete mobile,
       puoi collegarti a
       <strong><a href="https://data-lunch.duckdns.org/">data-lunch.duckdns.org</a></strong>.
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

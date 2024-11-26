# Modules
import re
import os
import json
import logging
import smtplib
from pprint import pprint
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid

class COMMON:
  # Config Variables
  user_config = None

  # Get JSON Config
  def get_user_data(self, file=None, broker=None):
    if file:
      self.user_config = file
    with open(self.user_config, "r") as h:
      data = json.load(h)

    logging.debug("User Config Data from: %s" % self.user_config)
    logging.debug(data)
    return data

  # Get a list of available python class files from a directory
  def get_class_list(self, directory):
    avail_class = []
    dir_list = os.listdir(directory)
    for each in dir_list:
      if re.search("class.py", each):
        each = each.replace('.py', '')
        avail_class.append(each)
    return avail_class

  # General read a json file
  def read_json(self, file=None):
    with open(file, "r") as h:
      try:
        data = json.load(h)
      except json.decoder.JSONDecodeError:
        data = {}
    return data

  # General write a json file
  def write_json(self, data, file=None):
    with open(file, "w+") as h:
      h.write(json.dumps(data))

  # Send Email
  def send_email(self, msg, email, subject, email_bypass=False):
    if email_bypass:
      print(msg)
      sys.exit()

    use_msg = "<HTML><BODY>"
    use_msg += msg
    use_msg += "</BODY></HTML>"

    # Generate Email Message
    try:
      raw_email = email.split('@')
      user = raw_email[0]
      domain = raw_email[1]
    except:
      logging.error("Email provide is malformed: %s" % email)
      sys.exit()

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = Address(email, user, domain)
    msg['To'] = Address(email, user, domain)
    msg.set_content("Yo")

    # This converts the message into a multipart/alternative
    # container, with the original text message as the first part 
    # and the new html message as the second part.
    asparagus_cid = make_msgid()
    msg.add_alternative(use_msg.format(asparagus_cid=asparagus_cid[1:-1]), subtype='html')

    # Send Email
    if email:
      logging.debug("Sending email to %s" % msg['To'])
      logging.debug("To: %s" % msg['To'])
      logging.debug("From: %s" % msg['From'])
      logging.debug("Subject: %s" % msg['Subject'])
      logging.debug("Body: %s" % msg.as_string)

      # Send the message via local SMTP server.
      with smtplib.SMTP('localhost') as s:
        s.send_message(msg)
        s.quit()
        logging.info("Email Sent")
    else:
      logging.error("No Email Address Provided")



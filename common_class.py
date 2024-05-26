# Modules
import re
import os
import json
import logging
from pprint import pprint

class COMMON:
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


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

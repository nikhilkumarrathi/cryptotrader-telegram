import json
import os
import log as log
if not os.path.exists('config/config.json'):
  log.error("The config.json file is missing")
  log.warn("-- copy the config.json.template file as config.json")
  log.warn("-- fill the Details")
  os._exit(0);

from dotmap import DotMap
configData = DotMap(json.load(open('config/config.json','r')))

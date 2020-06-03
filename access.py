from dotmap import DotMap
from config import configData
accessControl = DotMap(configData).accessControl
print(accessControl)

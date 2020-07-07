from dotmap import DotMap
from config import configData

accessControl = DotMap(configData).accessControl

if isinstance(accessControl.adminChatId ,str) and accessControl.adminChatId.isnumeric() :
    accessControl.adminChatId = int(accessControl.adminChatId)

print(accessControl)


from motor.motor_asyncio import AsyncIOMotorClient

mongourl = "mongodb://localhost:27017/"

engine = AsyncIOMotorClient(mongourl)

database = engine.get_database('notes')

# collections
workspaces = database.get_collection('workspace')
users = database.get_collection('users')
notes = database.get_collection('notes')
contents = database.get_collection('content') 
collabs = database.get_collection('collabs')


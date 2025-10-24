from pydantic import BaseModel, ConfigDict, RootModel, Field
from datetime import datetime


class NoteCreate(BaseModel):

    user_id : str
    workspace_id : str
    created_at : datetime = Field(default_factory=datetime.now)

    
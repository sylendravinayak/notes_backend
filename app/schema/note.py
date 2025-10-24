from pydantic import BaseModel, ConfigDict, RootModel, Field
from datetime import datetime


class NoteCreate(BaseModel):

    user_id : str
    workspace_id : str
    created_at : datetime = Field(default_factory=datetime.now)
    header : str

class Note(NoteCreate):

    note_id : str


class ContentCreate(BaseModel):

    section_no : int
    note_id : str
    content : str
    created_at : datetime = Field(default_factory=datetime.now)

class Content(ContentCreate):
    
    content_id : str


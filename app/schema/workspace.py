
from pydantic import BaseModel, ConfigDict, RootModel, Field
from datetime import datetime

class WorkSpaceCreate(BaseModel):

    workspace_name : str 
    user_id : str
    created_at : datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)

class WorkSpace(WorkSpaceCreate):

    workspace_id : str 



class AddUserToWorkSpace(BaseModel):

    user_id : str
    workspace_id : str
    access : str # it would be like r or rw

    model_config = ConfigDict(from_attributes=True)

class Collab(BaseModel):

    user_id : str
    workspace_id : str
    access : str # it would be like r or rw

    model_config = ConfigDict(from_attributes=True)

class Collabs(RootModel[list[Collab]]):

    pass


    




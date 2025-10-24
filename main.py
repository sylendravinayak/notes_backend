
from fastapi import FastAPI, APIRouter
from app.routes import note as note_rouer, user_routes, workspace as workspace_router

app = FastAPI()

app.include_router(user_routes.router)
app.include_router(workspace_router.router) 
app.include_router(note_rouer.router)
@app.get("/")
def root():
    return {"msg": "everything seems working fine"}

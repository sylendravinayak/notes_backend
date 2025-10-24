
from fastapi import FastAPI, APIRouter


app = FastAPI()

@app.get("/")
def root():

    return {"msg": "everything seems working fine"}


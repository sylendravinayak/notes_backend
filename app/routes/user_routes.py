from fastapi import APIRouter, HTTPException, status,Request
from schema.user_schema import UserBase
from models.users import User
from auth.hashing import hash_password, verify_password
from auth.jwt_handler import create_access_token
from database import workspaces
router = APIRouter()

@router.post("/sign-up/")
def create_user(user: UserBase):
    # Check if user with the same email already exists
    existing_user = User.get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )
    new_password = hash_password(user.password)
    # Create new user
    new_user = User.create_user(user.email, user.username, new_password)
    return {"message": "User created successfully", "user_id": str(new_user.id)}

@router.post("/login")
def login_user(user: UserBase):
    existing_user = User.get_user_by_email(user.email)
    if not existing_user or not verify_password(user.password, existing_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    token = create_access_token({"sub": str(existing_user.id),"workspace_name":"personal","workspace_id":str(existing_user.id),"access":"rw"})
    return {"token": token}


@router.get("/workspace/{workspace_id}/")
def get_workspace_token(workspace_id: str, depends=):
    # Logic to retrieve workspace information
    workspace = workspaces.find_one({"_id": workspace_id})


    
    return {"workspace": workspace}
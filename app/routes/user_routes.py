from fastapi import APIRouter, HTTPException, status,Depends
from schema.user_schema import UserBase
from models.users import User
from auth.hashing import hash_password, verify_password
from auth.jwt_handler import ALGORITHM, SECRET_KEY, create_access_token,oauth2_scheme
from database import workspaces,collabs
from jose import JWTError, jwt
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
    token = create_access_token({"user_id": str(existing_user.id),"workspace_name":"personal","workspace_id":str(existing_user.id),"access":"rw"})
    return {"token": token}


@router.get("/workspace/{workspace_id}/")
def get_workspace_token(workspace_id: str,token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token."
        )

    workspace = collabs.find_one({"workspace_id": workspace_id,"user_id": payload['user_id']})
    return  create_access_token({"user_id": payload['user_id'],"workspace_name":workspace['workspace_name'],"workspace_id":workspace['workspace_id'],"access":workspace['access']})
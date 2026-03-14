from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/token")
async def login_for_access_token():
    return {"access_token": "disabled", "token_type": "bearer"}

@router.get("/me")
async def read_users_me():
    return {"username": "admin"}

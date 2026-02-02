from fastapi import APIRouter, Depends
from app.auth.authentication import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
def me(user=Depends(authenticate_user)):
    return user

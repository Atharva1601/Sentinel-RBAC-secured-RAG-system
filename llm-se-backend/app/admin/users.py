from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.authentication import authenticate_user
from app.db.database import SessionLocal
from app.db.models import User
from app.models.admin_users import UserCreateRequest, UserUpdateRequest

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: dict):
    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="Admin privileges required")


@router.get("/users")
def list_users(user=Depends(authenticate_user)):
    require_admin(user)

    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        return [
            {
                "username": u.username,
                "role_level": u.role_level,
                "clearance_level": u.clearance_level,
                "department": u.department,
                "is_active": u.is_active,
            }
            for u in users
        ]
    finally:
        db.close()


@router.post("/users")
def create_user(
    payload: UserCreateRequest,
    user=Depends(authenticate_user),
):
    require_admin(user)

    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == payload.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        new_user = User(
            username=payload.username,
            role_level=payload.role_level,
            clearance_level=payload.clearance_level,
            department=payload.department,
            is_active=True,
        )

        db.add(new_user)
        db.commit()

        return {
            "status": "created",
            "username": payload.username,
        }

    finally:
        db.close()


@router.patch("/users/{username}")
def update_user(
    username: str,
    payload: UserUpdateRequest,
    user=Depends(authenticate_user),
):
    require_admin(user)

    db: Session = SessionLocal()
    try:
        target = db.query(User).filter(User.username == username).first()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        if username == "admin" and payload.is_active is False:
            raise HTTPException(
                status_code=400,
                detail="Admin user cannot be deactivated",
            )

        if payload.role_level is not None:
            target.role_level = payload.role_level

        if payload.clearance_level is not None:
            target.clearance_level = payload.clearance_level

        if payload.department is not None:
            target.department = payload.department

        if payload.is_active is not None:
            target.is_active = payload.is_active

        db.commit()

        return {
            "status": "updated",
            "username": username,
        }

    finally:
        db.close()


@router.delete("/users/{username}")
def delete_user(
    username: str,
    user=Depends(authenticate_user),
):
    """
    Permanently delete a user.
    Admin-only.
    """

    require_admin(user)

    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db: Session = SessionLocal()
    try:
        target = db.query(User).filter(User.username == username).first()

        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        db.delete(target)
        db.commit()

        return {
            "status": "deleted",
            "username": username,
        }

    finally:
        db.close()

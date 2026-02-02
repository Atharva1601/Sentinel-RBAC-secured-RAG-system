from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User

security = HTTPBearer(auto_error=False)


def authenticate_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Authentication layer.

    - Expects: Authorization: Bearer <username>
    - Validates user exists in DB
    - Validates user is active
    - Returns user metadata for RBAC
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme",
        )

    username = credentials.credentials.strip()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )

        return {
            "username": user.username,
            "department": user.department,
            "role_level": user.role_level,
            "clearance_level": user.clearance_level,
        }

    finally:
        db.close()

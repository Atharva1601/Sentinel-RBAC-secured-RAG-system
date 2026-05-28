from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.authentication import authenticate_user
from app.db.database import SessionLocal
from app.db.models import Department

router = APIRouter(prefix="/admin", tags=["admin"])


class DepartmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


def require_admin(user: dict):
    if user["role_level"] < 3:
        raise HTTPException(status_code=403, detail="Admin privileges required")


@router.get("/departments")
def list_departments(user=Depends(authenticate_user)):
    """
    List all departments. Available to any authenticated user.
    """
    db: Session = SessionLocal()
    try:
        departments = db.query(Department).all()
        return [
            {
                "id": dept.id,
                "name": dept.name,
                "created_at": dept.created_at,
            }
            for dept in departments
        ]
    finally:
        db.close()


@router.post("/departments")
def create_department(
    payload: DepartmentCreateRequest,
    user=Depends(authenticate_user),
):
    """
    Add a new department. Admin-only.
    """
    require_admin(user)
    
    # Normalize name (strip whitespace)
    dept_name = payload.name.strip()
    if not dept_name:
        raise HTTPException(status_code=400, detail="Department name cannot be empty or whitespace only")

    db: Session = SessionLocal()
    try:
        existing = db.query(Department).filter(Department.name == dept_name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Department already exists")

        new_dept = Department(name=dept_name)
        db.add(new_dept)
        db.commit()

        return {
            "status": "created",
            "name": dept_name,
        }
    finally:
        db.close()

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User, Department

# Default system departments
DEPARTMENTS = ["shared", "AI", "GenAI", "ML", "DL"]

# Default system users
USERS = [
    {
        "username": "admin",
        "role_level": 3,
        "clearance_level": 3,
        "department": "shared",
    },
    {
        "username": "analyst_ai",
        "role_level": 2,
        "clearance_level": 2,
        "department": "AI",
    },
    {
        "username": "intern_ai",
        "role_level": 1,
        "clearance_level": 1,
        "department": "AI",
    },
    {
        "username": "analyst_shared",
        "role_level": 2,
        "clearance_level": 2,
        "department": "shared",
    },
]


def seed_users_if_empty():
    db: Session = SessionLocal()
    try:
        # Seed departments first
        if not db.query(Department).first():
            for dept_name in DEPARTMENTS:
                db.add(Department(name=dept_name))
            db.commit()
            print("Default departments seeded successfully.")

        # Seed users if any user doesn't exist
        if not db.query(User).first():
            for user_data in USERS:
                db.add(User(**user_data))
            db.commit()
            print("Default users seeded successfully.")

    finally:
        db.close()


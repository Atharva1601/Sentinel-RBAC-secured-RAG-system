from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User

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
        # If any user exists, assume DB already seeded
        if db.query(User).first():
            return

        for user_data in USERS:
            db.add(User(**user_data))

        db.commit()
        print("✅ Default users seeded")

    finally:
        db.close()

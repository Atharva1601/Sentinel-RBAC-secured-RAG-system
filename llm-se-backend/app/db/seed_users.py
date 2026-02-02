from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import User


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


def seed_users():
    db: Session = SessionLocal()

    try:
        for user_data in USERS:
            existing = (
                db.query(User)
                .filter(User.username == user_data["username"])
                .first()
            )

            if existing:
                print(f"ℹ️ User already exists: {user_data['username']}")
                continue

            user = User(**user_data)
            db.add(user)
            print(f"✅ Added user: {user.username}")

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    seed_users()

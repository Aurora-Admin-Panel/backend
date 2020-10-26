#!/usr/bin/env python3

from app.db.session import get_db
from app.db.session import SessionLocal
from app.db.crud.user import create_user
from app.db.schemas.user import UserCreate


def init() -> None:
    db = SessionLocal()

    create_user(
        db,
        UserCreate(
            email="admin@example.com",
            password="1234qwer?!",
            is_active=True,
            is_superuser=True,
        ),
    )


if __name__ == "__main__":
    print("Creating superuser admin@example.com")
    init()
    print("Superuser created")

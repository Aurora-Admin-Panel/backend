from contextlib import contextmanager
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.core import config

engine = create_engine(
    config.SQLALCHEMY_DATABASE_URI,
    pool_size=20, max_overflow=5
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# Dependency
@contextmanager
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
    

def get_db(request: Request):
    return request.state.db

import os

PROJECT_NAME = "aurora-admin-panel"

SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
ENABLE_SENTRY = os.getenv("ENABLE_SENTRY", False)
SECRET_KEY = os.getenv("SECRET_KEY", "aurora-admin-panel")

API_V1_STR = "/api/v1"

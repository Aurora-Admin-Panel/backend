import os

PROJECT_NAME = "aurora-admin-panel"

BACKEND_VERSION = os.getenv("BACKEND_VERSION", '0.1.0')
ENVIRONMENT = os.getenv("ENVIRONMENT", "PROD")
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
SQLALCHEMY_ASYNC_DATABASE_URI = os.getenv("ASYNC_DATABASE_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
ENABLE_SENTRY = os.getenv("ENABLE_SENTRY", False)
SECRET_KEY = os.getenv("SECRET_KEY", "aurora-admin-panel")
TRAFFIC_INTERVAL_SECONDS = os.getenv("TRAFFIC_INTERVAL_SECONDS", 600)
DDNS_INTERVAL_SECONDS = os.getenv("DDNS_INTERVAL_SECONDS", 120)
SSH_CONNECTION_TIMEOUT = os.getenv("SSH_CONNECTION_TIMEOUT", 10)
FILE_STORAGE_PATH = os.getenv("FILE_STORAGE_PATH", "/app/files")
TASK_OUTPUT_STORAGE_DAYS = os.getenv("TASK_OUTPUT_STORAGE_DAYS", 1)
PUBSUB_PREFIX = os.getenv("PUBSUB_PREFIX", "aurora:pubsub")
PUBSUB_STOPWORD = os.getenv("PUBSUB_STOPWORD", "AURORA_PUBSUB_STOP")
PUBSUB_TIMEOUT_SECONDS = os.getenv("PUBSUB_TIMEOUT_SECONDS", 10)
PUBSUB_SLEEP_SECONDS = os.getenv("PUBSUB_SLEEP_SECONDS", 0.1)

API_V1_STR = "/api/v1"

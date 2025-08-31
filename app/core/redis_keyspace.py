from app.core import config

APP_PREFIX = (
    f"{config.PROJECT_NAME}:{config.ENVIRONMENT}:{config.BACKEND_VERSION}".lower()
)


def rkey(*parts: object) -> str:
    # safe, consistent, lowercased, colon-separated
    return ":".join([APP_PREFIX, *map(lambda p: str(p).lower(), parts)])


class Keys:
    # caching
    @staticmethod
    def cache_user(user_id: int) -> str:
        return rkey("cache", "user", user_id)

    @staticmethod
    def task_ids() -> str:
        return rkey("task", "ids")

    @staticmethod
    def task_stream(task_id: str) -> str:
        return rkey(config.PUBSUB_PREFIX, task_id, "stream")

    @staticmethod
    def server_usage_task(server_id: int) -> str:
        return rkey("server", "usage", "task", server_id)

    @staticmethod
    def server_metric_snapshot(server_id) -> str:
        return rkey("server", "metric", "snapshot", server_id)

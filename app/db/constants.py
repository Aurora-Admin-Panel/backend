import enum


class LimitActionEnum(int, enum.Enum):
    NO_ACTION = 0
    SPEED_LIMIT_10K = 1
    SPEED_LIMIT_100K = 2
    SPEED_LIMIT_1M = 3
    SPEED_LIMIT_10M = 4
    SPEED_LIMIT_30M = 5
    SPEED_LIMIT_100M = 6
    SPEED_LIMIT_1G = 7
    DELETE_RULE = 8

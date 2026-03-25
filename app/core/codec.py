import orjson


def dumps(obj) -> bytes:
    return orjson.dumps(obj)


def loads(data: bytes) -> dict:
    return orjson.loads(data)

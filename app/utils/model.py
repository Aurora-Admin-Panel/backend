from sqlalchemy import Table


def to_json(model: Table) -> dict:
    return {c.name: getattr(model, c.name) for c in model.__table__.columns}

from sqlalchemy.orm import class_mapper

def model_to_dict(model):
    """Converts a SQLAlchemy model instance into a dictionary."""
    if model is None:
        return None
    return {c.key: getattr(model, c.key) for c in class_mapper(model.__class__).columns}
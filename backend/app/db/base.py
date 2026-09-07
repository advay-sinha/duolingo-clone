"""The declarative base every ORM model inherits from.

Kept in its own module to avoid circular imports: models import ``Base`` from
here, and the metadata-consuming code (``init_db``) imports the models. If
``Base`` lived beside the engine, importing a model would drag the engine —
and therefore a database connection — into every import.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base.

    Subclasses register themselves on ``Base.metadata``, which is what
    ``create_all`` reads to emit ``CREATE TABLE`` statements.
    """

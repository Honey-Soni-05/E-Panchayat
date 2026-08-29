"""Alembic's view of the schema.

Importing this module registers every table on ``Base.metadata`` so that
``alembic revision --autogenerate`` can diff the models against the database.
"""

from app.db.base_class import Base  # noqa: F401
from app import models  # noqa: F401  (imported for its registration side effect)

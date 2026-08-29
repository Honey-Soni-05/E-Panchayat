"""The declarative base every model inherits from.

Kept in its own module so `app.models` can import it without the circular
import that would arise from importing `app.db.base` (which pulls in models).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# Base class that every table model inherits from.
# SQLAlchemy keeps a list of all the tables

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
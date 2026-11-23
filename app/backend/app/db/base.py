# Base class that every table model inherits from.
# SQLAlchemy keeps a list of all the tables

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import BigInteger, Integer


class Base(DeclarativeBase):
    pass


# BIGINT for primary key on Postgres that auto numbers
# integer keys
BigIntPK = BigInteger().with_variant(Integer, "sqlite")

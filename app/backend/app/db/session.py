# Creates connect to Supabase and the get_db function gives each request
# their own database session. 

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_kwargs: dict = {"pool_pre_ping": True}
# skips client side connection pooling
if os.getenv("VERCEL"):
    _kwargs["poolclass"] = NullPool

engine = create_engine(get_settings().database_url, **_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# creates table from the model and runes it onces 
# and again if any other models are added

import app.models
from app.db.base import Base
from app.db.session import engine

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("Tables created:", ", ".join(sorted(Base.metadata.tables)))
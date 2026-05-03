from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config
from models import Base

engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
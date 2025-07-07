from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Use SQLite, and store the database file at ./creditcard.db, relative to the current working directory.
SQLALCHEMY_DATABASE_URL = "sqlite:///./creditcard.db"

engine = create_engine(
	SQLALCHEMY_DATABASE_URL,
	connect_args={"check_same_thread": False}
)

# sessionmaker: Factory for creating session objects - each one represents a DB transaction
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Creates a base class from which all ORM models like table will inherit
Base = declarative_base()
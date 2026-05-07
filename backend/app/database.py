import os

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv(find_dotenv(), override=False)

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres:password@localhost:5432/recipe_planner"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS nutrition json"))
        connection.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS scraped_html text"))
        connection.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS extracted_text text"))
        connection.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS llm_response json"))
        connection.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS extraction_status varchar DEFAULT 'success'"))
        connection.execute(text("ALTER TABLE recipes ALTER COLUMN servings TYPE varchar USING servings::varchar"))
        connection.execute(text("ALTER TABLE recipes ALTER COLUMN title DROP NOT NULL"))
        connection.execute(text("ALTER TABLE recipes ALTER COLUMN extraction_status DROP NOT NULL"))
        connection.execute(text("ALTER TABLE recipes ALTER COLUMN extraction_status SET DEFAULT 'success'"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from .database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    cuisine = Column(String, nullable=True)
    prep_time = Column(String, nullable=True)
    cook_time = Column(String, nullable=True)
    total_time = Column(String, nullable=True)
    servings = Column(String, nullable=True)
    difficulty = Column(String, nullable=True)

    ingredients = Column(JSON, nullable=True)
    instructions = Column(JSON, nullable=True)
    nutrition = Column(JSON, nullable=True)
    substitutions = Column(JSON, nullable=True)
    shopping_list = Column(JSON, nullable=True)
    related_recipes = Column(JSON, nullable=True)

    scraped_html = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    llm_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def nutrition_estimate(self):
        return self.nutrition

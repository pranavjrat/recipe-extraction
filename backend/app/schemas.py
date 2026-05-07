from datetime import datetime
from typing import List, Optional, Union

from pydantic import AnyUrl, BaseModel


class Ingredient(BaseModel):
    quantity: Optional[str]
    unit: Optional[str]
    item: str


class Nutrition(BaseModel):
    calories: Optional[int]
    protein: Optional[str]
    carbs: Optional[str]
    fat: Optional[str]


class RecipeCreate(BaseModel):
    url: AnyUrl
    raw_html: Optional[str] = None
    raw_text: Optional[str] = None


class RecipeResponse(BaseModel):
    id: int
    url: AnyUrl
    title: Optional[str]
    cuisine: Optional[str]
    prep_time: Optional[str]
    cook_time: Optional[str]
    total_time: Optional[str]
    servings: Optional[Union[int, str]]
    difficulty: Optional[str]
    ingredients: Optional[List[Ingredient]]
    instructions: Optional[List[str]]
    nutrition: Optional[Nutrition]
    nutrition_estimate: Optional[Nutrition]
    substitutions: Optional[List[str]]
    shopping_list: Optional[dict]
    related_recipes: Optional[List[str]]
    created_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
    }


class RecipeListItem(BaseModel):
    id: int
    url: AnyUrl
    title: Optional[str]
    cuisine: Optional[str]
    difficulty: Optional[str]
    created_at: Optional[datetime]

    model_config = {
        "from_attributes": True,
    }


class MealPlanRequest(BaseModel):
    recipe_ids: List[int]


class MealPlanDay(BaseModel):
    day: int
    recipe: str


class MealPlanResponse(BaseModel):
    meal_plan: List[MealPlanDay]
    combined_shopping_list: dict

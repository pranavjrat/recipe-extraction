from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import logging

from .database import Base, engine, get_db
from .models import Recipe
from .schemas import RecipeCreate, RecipeResponse, RecipeListItem, MealPlanRequest, MealPlanResponse
from .extractor import RecipeExtractor
from .meal_planner import MealPlanner

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Recipe Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)
extractor = RecipeExtractor()
meal_planner = MealPlanner()


@app.post('/api/extract', response_model=RecipeResponse, status_code=201)
def extract_recipe(payload: RecipeCreate, db: Session = Depends(get_db)):
    url = str(payload.url)
    existing = db.query(Recipe).filter(Recipe.url == url).first()
    if existing:
        return existing

    try:
        result = extractor.extract(url, raw_html=payload.raw_html, raw_text=payload.raw_text)

        db_recipe = Recipe(
            url=result.get('url'),
            title=result.get('title'),
            cuisine=result.get('cuisine'),
            prep_time=result.get('prep_time'),
            cook_time=result.get('cook_time'),
            total_time=result.get('total_time'),
            servings=str(result.get('servings')) if result.get('servings') else None,
            difficulty=result.get('difficulty'),
            ingredients=result.get('ingredients'),
            instructions=result.get('instructions'),
            nutrition=result.get('nutrition'),
            substitutions=result.get('substitutions'),
            shopping_list=result.get('shopping_list'),
            related_recipes=result.get('related_recipes'),
            scraped_html=result.get('scraped_html')
        )

        db.add(db_recipe)
        db.commit()
        db.refresh(db_recipe)

        return db_recipe

    except PermissionError as e:
        logger.warning(f"Blocked recipe site: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/recipes', response_model=list[RecipeListItem])
def list_recipes(db: Session = Depends(get_db)):
    items = db.query(Recipe).order_by(Recipe.created_at.desc()).all()
    return items


@app.get('/api/recipes/{recipe_id}', response_model=RecipeResponse)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)):
    item = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not item:
        raise HTTPException(status_code=404, detail='Recipe not found')
    return item


@app.post('/api/meal-plan', response_model=MealPlanResponse)
def create_meal_plan(payload: MealPlanRequest, db: Session = Depends(get_db)):
    recipes = db.query(Recipe).filter(Recipe.id.in_(payload.recipe_ids)).all()
    if not recipes:
        raise HTTPException(status_code=404, detail='No recipes found for meal planning')

    data = []
    for recipe in recipes:
        data.append({
            'id': recipe.id,
            'title': recipe.title,
            'ingredients': recipe.ingredients or [],
            'shopping_list': recipe.shopping_list or {},
        })

    result = meal_planner.build_plan(data)
    return result


@app.get('/health')
def health():
    return {'status': 'ok'}

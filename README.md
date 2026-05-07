# Recipe Extractor & Meal Planner

This repository now contains a fresh implementation of the Recipe Extractor & Meal Planner assignment.

It provides:

- a FastAPI backend that scrapes recipe blog URLs and stores extracted recipes in a database
- a clean, minimal frontend with two tabs: extraction and saved history
- prompt templates for recipe extraction, nutrition estimation, and substitutions
- an optional meal-planner endpoint that merges saved recipe shopping lists
- sample URLs and sample JSON outputs under `sample_data/`

## Project Layout

- `backend/` - FastAPI backend implementation
- `frontend/` - recipe extraction UI used by the assignment
- `prompts/` - LangChain prompt templates
- `sample_data/` - example URLs and example API output
- `run_app.sh` - convenience script that starts the backend and frontend together
- `docker-compose.yml` - PostgreSQL container for the required database layer
- `.env.example` - sample environment variables for PostgreSQL and the LLM key

## Technical Requirements

- Backend: FastAPI
- Database: PostgreSQL only
- Frontend: minimal HTML, CSS, and JavaScript
- LLM: LangChain with Gemini via `GEMINI_API_KEY` or Groq via `GROQ_API_KEY`
- Scraping: BeautifulSoup over recipe blog HTML pages
- Data source: recipe blog URLs only, no external recipe APIs

## Run The App

From the repository root, start both servers with:

```bash
bash run_app.sh
```

The script uses `backend/.venv` when available, launches the backend at `http://127.0.0.1:8001`, and starts the frontend on `http://127.0.0.1:3000` or the next free port if 3000 is already in use.

Press `Ctrl+C` in the terminal to stop both processes.

## PostgreSQL Setup

Copy the example environment file and start PostgreSQL:

```bash
cp .env.example .env
docker compose up -d db
```

Or start PostgreSQL directly with Docker:

```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=recipe_planner \
  -p 5432:5432 \
  postgres:15
```

Then run the backend from `backend/` so it picks up `DATABASE_URL` from `.env`:

```bash
cd backend
uvicorn app.main:app --reload --port 8001
```

If you use the root launcher, it will still start the frontend and backend together. PostgreSQL must be running before the backend starts.

## Backend Setup

Install dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload --port 8001
```

Environment variables:

```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/recipe_planner
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-1.5-flash
# or:
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

Recipe extraction requires one valid LLM key. The backend scrapes the recipe page, cleans the HTML with BeautifulSoup, sends the extracted text to the configured LangChain chat model, validates the JSON response, and stores both the scraped text and generated JSON in PostgreSQL.

## Frontend Setup

The frontend is static HTML, CSS, and JavaScript.

You can open `frontend/index.html` directly or serve the folder with a local static server.

The frontend expects the API to run at `http://localhost:8001`.

## API Endpoints

### Extract a Recipe

`POST /api/extract`

Request body:

```json
{ "url": "https://www.allrecipes.com/recipe/23891/grilled-cheese-sandwich/" }
```

If a recipe site blocks automated scraping, you can also send optional `raw_text` or `raw_html` in the request body and the backend will extract from that content instead of fetching the page.

### List Saved Recipes

`GET /api/recipes`

### Get Recipe Details

`GET /api/recipes/{id}`

### Generate Meal Plan

`POST /api/meal-plan`

Request body:

```json
{ "recipe_ids": [1, 2, 3] }
```

Returns a small day-by-day meal plan and a merged shopping list for the selected saved recipes.

## Testing Steps

1. Start the backend.
2. Open the frontend.
3. Paste one of the URLs from `sample_data/urls.txt`.
4. Confirm the structured recipe renders in the extraction tab.
5. Switch to Saved Recipes and open a Details modal from the table.
6. Select at least three saved recipes and generate a meal plan.

## Screenshots

## Recipe Details

![Recipe Details](screenshots/Pasted%20image%2020260506092741.png)

## Recipe History

![Recipe History](screenshots/Pasted%20image%2020260506092755.png)

## Details Section in Tab 2

![Details Section in Tab 2](screenshots/Pasted%20image%2020260506100845.png) 

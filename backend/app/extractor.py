import os
import json
from typing import Any, Dict
from bs4 import BeautifulSoup

from .scraper import RecipeScraper

try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False


class RecipeExtractor:
    """
    Extracts and enriches recipe data from HTML pages.
    
    Features:
    - JSON-LD structured data extraction (primary, most reliable)
    - Heuristic HTML parsing fallback for unstructured pages
    - Ingredient parsing with quantity/unit/item separation
    - Difficulty inference from instruction count
    - Nutrition estimation based on serving size
    - Ingredient substitution suggestions
    - Related recipe recommendations
    - Shopping list categorization by food type
    
    The LLM (Groq) is optional; all features work with heuristics.
    """
    def __init__(self):
        self.scraper = RecipeScraper()
        self.llm = None
        if LLM_AVAILABLE:
            api_key = os.getenv('GROQ_API_KEY') or os.getenv('LLM_API_KEY')
            if api_key:
                self.llm = ChatGroq(api_key=api_key, model="llama-3.1-8b-instant", temperature=0.2)

    def extract(self, url: str, raw_html: str | None = None, raw_text: str | None = None) -> Dict[str, Any]:
        """Extract recipe from URL, raw HTML, or raw text.
        
        Args:
            url: Recipe page URL (or identifier if using raw_html/raw_text)
            raw_html: Optional pre-fetched HTML content (bypasses fetch)
            raw_text: Optional raw recipe text (auto-wrapped as HTML)
        
        Returns:
            Dict with keys: title, cuisine, prep_time, cook_time, total_time, servings,
            difficulty, ingredients (parsed: qty/unit/item), instructions, nutrition,
            substitutions, shopping_list (categorized), related_recipes, url, scraped_html.
        
        Raises:
            PermissionError: If site blocks automated access (HTTP 403)
            requests.HTTPError: For other HTTP errors
        """
        if raw_html:
            html, final_url = raw_html, url
            return self._extract_from_html(html, final_url)

        if raw_text:
            # Wrap raw text as simple HTML for consistent processing
            html = f"<html><body>{''.join(f'<p>{line.strip()}</p>' for line in raw_text.splitlines() if line.strip())}</body></html>"
            return self._extract_from_html(html, url)

        html, final_url = self.scraper.fetch(url)
        return self._extract_from_html(html, final_url or url)

    def _extract_from_html(self, html: str, source_url: str) -> Dict[str, Any]:
        """Core extraction: parse HTML and enrich recipe fields.
        
        Extraction priority:
        1. JSON-LD structured data (most reliable, industry standard)
        2. Heuristic HTML parsing (fallback for unstructured pages)
        3. Page h1 tag (final fallback for title)
        
        Then applies post-processing: ingredient parsing, difficulty inference,
        nutrition estimation, substitution suggestions, shopping categorization,
        and related recipe recommendations.
        """
        html = html or ""

        # Primary: Try JSON-LD structured data (most sites include this)
        jsonld = self.scraper.extract_json_ld(html)
        result: Dict[str, Any] = {}
        if jsonld:
            # JSON-LD provides clean, machine-readable recipe data per schema.org
            result['title'] = jsonld.get('name')
            result['cuisine'] = jsonld.get('recipeCuisine')
            result['prep_time'] = jsonld.get('prepTime')
            result['cook_time'] = jsonld.get('cookTime')
            result['total_time'] = jsonld.get('totalTime')
            result['servings'] = jsonld.get('recipeYield')
            result['ingredients_raw'] = jsonld.get('recipeIngredient') or jsonld.get('ingredients') or []
            # Handle both single instruction (string) and list of instructions (objects or strings)
            instructions = []
            instr = jsonld.get('recipeInstructions')
            if isinstance(instr, list):
                for step in instr:
                    if isinstance(step, dict):
                        instructions.append(step.get('text'))
                    else:
                        instructions.append(str(step))
            elif isinstance(instr, str):
                instructions = [instr]
            result['instructions'] = [s for s in instructions if s]
        else:
            # Fallback: heuristic extraction for pages without structured data
            heur = self.scraper.heuristic_extract(html)
            result['title'] = heur.get('title')
            result['ingredients_raw'] = heur.get('ingredients', [])
            result['instructions'] = heur.get('instructions', [])

        # Final title fallback: look for h1 tag if title still missing
        if not result.get('title'):
            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('h1')
            if title_tag:
                result['title'] = title_tag.get_text().strip()

        result['url'] = source_url
        # Store truncated HTML for audit/debugging (first 50KB)
        result['scraped_html'] = html[:50000]

        # INGREDIENT PARSING: Separate quantity, unit, and item name.
        # Heuristic: if first token is numeric/contains digits → quantity
        #            if next token is short (≤4 chars) and likely unit → unit
        #            remainder → item name
        # Examples: "2 cups flour" → qty=2, unit=cups, item=flour
        #           "1/4 tsp salt" → qty=1/4, unit=tsp, item=salt
        #           "fresh basil" → qty=None, unit=None, item=fresh basil
        parsed_ingredients = []
        for ing in result.get('ingredients_raw', []):
            qty = None
            unit = None
            item = ing
            parts = ing.split()
            # Check if first token looks like a quantity (numeric)
            if parts and (parts[0].replace('/', '').replace('-', '').replace('.', '').isdigit() or any(ch.isdigit() for ch in parts[0])):
                # First token is a quantity (e.g., "2", "1/4", "2-3")
                qty = parts[0]
                # Check if next token is a likely unit (short, common abbreviations)
                if len(parts) > 1 and len(parts[1]) <= 4:
                    unit = parts[1]
                    item = ' '.join(parts[2:]) if len(parts) > 2 else ''
                else:
                    # Next token is too long; treat as part of item
                    item = ' '.join(parts[1:])
            parsed_ingredients.append({'quantity': qty, 'unit': unit, 'item': item})

        result['ingredients'] = parsed_ingredients

        # DIFFICULTY INFERENCE: Based on number of instruction steps
        # Heuristic: easy (1-4 steps) → quick meals
        #            medium (5-10 steps) → standard recipes
        #            hard (11+ steps) → complex techniques
        instr_count = len(result.get('instructions') or [])
        if instr_count <= 4:
            difficulty = 'easy'
        elif instr_count <= 10:
            difficulty = 'medium'
        else:
            difficulty = 'hard'
        result['difficulty'] = difficulty

        # NUTRITION ESTIMATION: Simple model based on serving count
        # Baseline: ~200 cal/serving (heuristic average for recipes)
        # Macro split: 10% protein, 40% carbs, 30% fat (typical balanced diet)
        # Used when LLM is unavailable; better estimates come from ingredient analysis
        servings = 1
        serv_val = result.get('servings')
        if serv_val:
            try:
                import re
                m = re.search(r"(\d+)", str(serv_val))
                if m:
                    servings = int(m.group(1))
            except Exception:
                # If parsing fails, default to 1 serving
                servings = 1

        calories = max(100, 200 * servings)
        result['nutrition'] = {'calories': calories, 'protein': f"{int(calories*0.1)}g", 'carbs': f"{int(calories*0.4)}g", 'fat': f"{int(calories*0.3)}g"}

        # SUBSTITUTION SUGGESTIONS: Recommend dietary alternatives based on ingredients
        # Strategy: detect common ingredients and suggest health/dietary alternatives
        # Examples: butter → olive oil (heart health), milk → plant-based (lactose-free)
        subs = []
        items_text = ' '.join([i['item'].lower() for i in parsed_ingredients if i.get('item')])
        if 'butter' in items_text:
            subs.append('Replace butter with olive oil for a dairy-free option.')
        if 'milk' in items_text:
            subs.append('Use almond milk or oat milk as a dairy-free replacement for milk.')
        if 'sugar' in items_text:
            subs.append('Replace granulated sugar with honey or maple syrup (adjust liquids).')
        # Add generic substitutions if we have fewer than 3
        generic = ["Use whole wheat alternatives where applicable.", "Use Greek yogurt instead of sour cream for tang and protein."]
        for g in generic:
            if len(subs) >= 3:
                break
            if g not in subs:
                subs.append(g)
        # Return up to 3 substitutions
        result['substitutions'] = subs[:3]

        # SHOPPING LIST: Categorize ingredients for organized store navigation
        # Categories: dairy, produce, pantry, bakery, spices (matches typical grocery layout)
        categories = {'dairy': [], 'produce': [], 'pantry': [], 'bakery': [], 'spices': []}
        for ing in parsed_ingredients:
            it = (ing.get('item') or '').lower()
            # Use keyword matching to categorize each ingredient
            if any(x in it for x in ['cheese', 'milk', 'butter', 'yogurt']):
                categories['dairy'].append(it)
            elif any(x in it for x in ['onion', 'garlic', 'tomato', 'lemon', 'potato', 'pepper']):
                categories['produce'].append(it)
            elif any(x in it for x in ['bread', 'baguette']):
                categories['bakery'].append(it)
            elif any(x in it for x in ['salt', 'pepper', 'cumin', 'paprika']):
                categories['spices'].append(it)
            elif it:
                # Catch-all for anything else (oils, grains, canned goods, etc.)
                categories['pantry'].append(it)
        # Remove duplicates and exclude empty categories
        shopping = {k: list(dict.fromkeys(v)) for k, v in categories.items() if v}
        result['shopping_list'] = shopping

        # RELATED RECIPES: Suggest complementary dishes based on recipe type
        # Strategy: detect dish type from title keywords and recommend pairings
        related = []
        if result.get('title'):
            t = result['title'].lower()
            if 'grilled' in t or 'sandwich' in t:
                # Grilled/sandwich recipes pair well with soups and salads
                related = ['Tomato Soup', 'Caprese Sandwich', 'French Onion Grilled Cheese']
            elif 'chicken' in t:
                # Chicken dishes pair well with vegetable sides and starches
                related = ['Roasted Vegetables', 'Mashed Potatoes', 'Green Salad']
        result['related_recipes'] = related

        return result

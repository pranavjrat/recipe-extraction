import json
import os
import re
import logging
from pathlib import Path
from typing import Any, Dict

from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage

from .scraper import RecipeScraper

logger = logging.getLogger(__name__)

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:
    ChatGoogleGenerativeAI = None

try:
    from langchain_groq import ChatGroq
except Exception:
    ChatGroq = None


class RecipeExtractor:
    """
    Scrape a recipe page, clean the HTML with BeautifulSoup, and send the
    extracted text to an LLM. The LLM returns the complete structured recipe
    and generated enrichment fields required by the assignment.
    """

    def __init__(self):
        self.scraper = RecipeScraper()
        base_dir = Path(__file__).resolve().parents[2]
        self.recipe_prompt_path = base_dir / "prompts" / "prompt_recipe.txt"
        self.llm = self._build_llm()

    def extract(self, url: str, raw_html: str | None = None, raw_text: str | None = None) -> Dict[str, Any]:
        if raw_html:
            html, final_url = raw_html, url
        elif raw_text:
            html, final_url = self._text_to_html(raw_text), url
        else:
            html, final_url = self.scraper.fetch(url)

        scraped_text = self._extract_text_with_beautifulsoup(html)
        if not scraped_text:
            raise ValueError("No readable recipe text could be extracted from the page.")

        recipe = self._extract_recipe_with_llm(scraped_text)
        recipe = self._normalize_recipe(recipe)
        recipe["url"] = final_url or url
        recipe["scraped_html"] = html[:5000]
        recipe["extracted_text"] = scraped_text[:5000]
        recipe["llm_response"] = {
            key: value
            for key, value in recipe.items()
            if key not in {"scraped_html", "extracted_text", "llm_response"}
        }
        return recipe

    def _build_llm(self):
        # Prioritize Groq (free tier is reliable)
        groq_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
        if groq_key:
            if ChatGroq is None:
                return None
            return ChatGroq(
                api_key=groq_key,
                model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                temperature=0.1,
            )

        # Fall back to Gemini if Groq not available
        gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            if ChatGoogleGenerativeAI is None:
                return None
            return ChatGoogleGenerativeAI(
                google_api_key=gemini_key,
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                temperature=0.1,
            )

        return None

    def _extract_recipe_with_llm(self, scraped_text: str) -> Dict[str, Any]:
        if self.llm is None:
            raise RuntimeError(
                "Configure GEMINI_API_KEY or a valid GROQ_API_KEY. "
                "Recipe extraction requires sending scraped BeautifulSoup text to an LLM via LangChain."
            )
        prompt_template = self.recipe_prompt_path.read_text(encoding="utf-8")
        prompt = prompt_template.replace("{scraped_text}", scraped_text[:6000])
        
        logger.debug(f"Sending to LLM {len(scraped_text)} chars of text")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        text = response.content if hasattr(response, "content") else str(response)
        
        logger.debug(f"LLM raw response ({len(text)} chars): {text[:300]}")
        
        try:
            data = self._parse_json(text)
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON: {str(e)}")
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)[:200]}. First 800 chars: {text[:800]}")
        
        if not isinstance(data, dict):
            logger.error(f"LLM response is not dict: {type(data).__name__}")
            raise ValueError(f"LLM did not return a JSON object. Got: {type(data).__name__}")
        
        logger.debug(f"Parsed recipe: title={data.get('title')}, ingredients={len(data.get('ingredients', []))}, instructions={len(data.get('instructions', []))}")
        return data

    def _extract_text_with_beautifulsoup(self, html: str) -> str:
        soup = BeautifulSoup(html or "", "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()

        useful_blocks: list[str] = []
        # Prioritized selectors to find recipe content
        selectors = [
            "[class*=ingredient]",
            "[id*=ingredient]",
            "[class*=instruction]",
            "[id*=instruction]",
            "[class*=direction]",
            "[id*=direction]",
            "[class*=recipe]",
            "[id*=recipe]",
            "[class*=method]",
            "[id*=method]",
            "h1",
            "[class*=nutrition]",
            "[class*=summary]",
            "main",
            "article",
        ]

        seen: set[str] = set()
        for selector in selectors:
            try:
                for node in soup.select(selector):
                    text = self._clean_text(node.get_text("\n"))
                    if text and text not in seen and len(text) > 10:
                        seen.add(text)
                        useful_blocks.append(text)
            except Exception:
                continue

        # If we didn't find much, add the full body text
        if len(useful_blocks) < 3:
            body_text = self._clean_text(soup.get_text("\n"))
            if body_text and body_text not in seen:
                useful_blocks.append(body_text)

        result = "\n\n".join(useful_blocks)[:6000]
        if not result.strip():
            raise ValueError("No readable content extracted from HTML")
        return result

    def _normalize_recipe(self, recipe: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = recipe.get("ingredients") or []
        if not isinstance(ingredients, list):
            ingredients = []
        ingredients = [self._normalize_ingredient(item) for item in ingredients]
        ingredients = [item for item in ingredients if item.get("item")]

        instructions = recipe.get("instructions") or []
        if isinstance(instructions, str):
            instructions = [instructions]
        instructions = [str(step).strip() for step in instructions if str(step).strip()]

        nutrition = recipe.get("nutrition_estimate") or recipe.get("nutrition") or {}
        if not isinstance(nutrition, dict):
            nutrition = {}

        substitutions = recipe.get("substitutions") or []
        if isinstance(substitutions, str):
            substitutions = [substitutions]
        substitutions = [str(item).strip() for item in substitutions if str(item).strip()][:3]
        
        related = recipe.get("related_recipes") or []
        if isinstance(related, str):
            related = [related]
        related = [str(item).strip() for item in related if str(item).strip()][:3]
        
        shopping = recipe.get("shopping_list") or {}
        if not isinstance(shopping, dict):
            shopping = {}

        normalized = {
            "title": self._nullable_string(recipe.get("title")),
            "cuisine": self._nullable_string(recipe.get("cuisine")),
            "prep_time": self._nullable_string(recipe.get("prep_time")),
            "cook_time": self._nullable_string(recipe.get("cook_time")),
            "total_time": self._nullable_string(recipe.get("total_time")),
            "servings": recipe.get("servings"),
            "difficulty": self._normalize_difficulty(recipe.get("difficulty"), instructions),
            "ingredients": ingredients,
            "instructions": instructions,
            "nutrition": self._normalize_nutrition(nutrition),
            "nutrition_estimate": self._normalize_nutrition(nutrition),
            "substitutions": substitutions,
            "shopping_list": shopping if isinstance(shopping, dict) else {},
            "related_recipes": related,
        }

        # Validation
        if not normalized["title"]:
            raise ValueError(f"MISSING: Recipe title is required. LLM returned: {recipe.get('title')}")
        if not normalized["ingredients"]:
            raise ValueError(f"MISSING: At least 1 ingredient is required. LLM returned: {ingredients}")
        if not normalized["instructions"]:
            raise ValueError(f"MISSING: At least 1 instruction is required. LLM returned: {instructions}")
        if not normalized["substitutions"] or len(normalized["substitutions"]) < 3:
            logger.warning(f"WARNING: Expected 3 substitutions, got {len(normalized['substitutions'])}")
        if not normalized["related_recipes"] or len(normalized["related_recipes"]) < 3:
            logger.warning(f"WARNING: Expected 3 related recipes, got {len(normalized['related_recipes'])}")
        if not normalized["shopping_list"] or len(normalized["shopping_list"]) < 2:
            logger.warning(f"WARNING: Expected shopping list with 2+ categories, got {len(normalized.get('shopping_list', {}))}")

        return normalized

    def _normalize_ingredient(self, value: Any) -> Dict[str, str | None]:
        if isinstance(value, dict):
            return {
                "quantity": self._nullable_string(value.get("quantity")),
                "unit": self._nullable_string(value.get("unit")),
                "item": self._nullable_string(value.get("item")) or "",
            }

        text = str(value).strip()
        match = re.match(r"^([\d./\-\s]+)?\s*([A-Za-z]+)?\s+(.+)$", text)
        if match:
            quantity = self._nullable_string(match.group(1))
            unit = self._nullable_string(match.group(2))
            item = self._nullable_string(match.group(3)) or text
            return {"quantity": quantity, "unit": unit, "item": item}
        return {"quantity": None, "unit": None, "item": text}

    def _normalize_nutrition(self, value: Dict[str, Any]) -> Dict[str, Any]:
        calories = value.get("calories")
        try:
            calories = int(calories) if calories is not None else None
        except Exception:
            calories = None
        return {
            "calories": calories,
            "protein": self._nullable_string(value.get("protein")),
            "carbs": self._nullable_string(value.get("carbs")),
            "fat": self._nullable_string(value.get("fat")),
        }

    def _normalize_difficulty(self, value: Any, instructions: list[str]) -> str:
        text = str(value or "").strip().lower()
        if text in {"easy", "medium", "hard"}:
            return text
        if len(instructions) <= 4:
            return "easy"
        if len(instructions) <= 10:
            return "medium"
        return "hard"

    def _parse_json(self, text: str) -> Any:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error at {e.pos}: {e.msg}")
            # Try to extract valid JSON
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start == -1 or end <= start:
                raise ValueError(f"No JSON object found in response: {cleaned[:200]}")
            
            json_str = cleaned[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try to repair common issues
                # Remove trailing commas before } or ]
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Last resort: try to close unclosed arrays
                    open_brackets = json_str.count('[') - json_str.count(']')
                    open_braces = json_str.count('{') - json_str.count('}')
                    if open_brackets > 0 or open_braces > 0:
                        json_str += ']' * open_brackets + '}' * open_braces
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            pass
                    raise ValueError(f"Could not parse JSON from LLM response. Last 500 chars: {cleaned[-500:]}")

    def _clean_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)

    def _nullable_string(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        text = str(value).strip()
        if not text or text.lower() in {"null", "none", "n/a"}:
            return None
        return text

    def _text_to_html(self, text: str) -> str:
        paragraphs = "".join(f"<p>{line.strip()}</p>" for line in text.splitlines() if line.strip())
        return f"<html><body>{paragraphs}</body></html>"

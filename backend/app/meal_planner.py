import json
import os
from pathlib import Path
from typing import Any, Dict, List
from fractions import Fraction

from langchain_core.messages import HumanMessage

try:
    from langchain_groq import ChatGroq
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False


class MealPlanner:
    def __init__(self):
        self.llm = None
        if LLM_AVAILABLE:
            api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
            if api_key:
                self.llm = ChatGroq(api_key=api_key, model="llama-3.1-8b-instant", temperature=0.2)

        base_dir = Path(__file__).resolve().parent.parent
        self.prompt_path = base_dir / "prompts" / "prompt_meal_plan.txt"

    def build_plan(self, recipes: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.llm and self.prompt_path.exists():
            with self.prompt_path.open("r", encoding="utf-8") as handle:
                template = handle.read()
            prompt = template.format(recipes_json=json.dumps(recipes, ensure_ascii=False))
            response = self.llm.invoke([HumanMessage(content=prompt)])
            text = response.content if hasattr(response, "content") else str(response)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except Exception:
                    pass

        meal_plan = []
        combined: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for index, recipe in enumerate(recipes[:3], start=1):
            meal_plan.append({"day": index, "recipe": recipe.get("title") or f"Recipe {index}"})

            for ingredient in recipe.get("ingredients") or []:
                item = str(ingredient.get("item") or "").strip().lower()
                if not item:
                    continue
                unit = str(ingredient.get("unit") or "").strip().lower()
                category = self._classify_item(item)
                bucket = combined.setdefault(category, {})
                key = f"{item}|{unit}"
                current = bucket.setdefault(key, {"item": item, "unit": unit, "quantity": Fraction(0)})
                current["quantity"] += self._parse_quantity(ingredient.get("quantity"))

            for category, items in (recipe.get("shopping_list") or {}).items():
                bucket = combined.setdefault(category, {})
                for item in items or []:
                    normalized = str(item).strip().lower()
                    if not normalized:
                        continue
                    key = f"{normalized}|"
                    bucket.setdefault(key, {"item": normalized, "unit": "", "quantity": Fraction(0)})

        formatted: Dict[str, List[str]] = {}
        for category, entries in combined.items():
            lines: List[str] = []
            for entry in entries.values():
                quantity = self._format_quantity(entry["quantity"])
                unit = entry["unit"].strip()
                item = entry["item"]
                parts = [part for part in [quantity, unit, item] if part]
                lines.append(" ".join(parts))
            formatted[category] = sorted(dict.fromkeys(lines))

        return {"meal_plan": meal_plan, "combined_shopping_list": formatted}

    def _parse_quantity(self, value: Any) -> Fraction:
        if value is None:
            return Fraction(1)

        text = str(value).strip()
        if not text:
            return Fraction(1)

        parts = text.split()
        total = Fraction(0)
        for part in parts:
            try:
                total += Fraction(part)
            except Exception:
                continue

        if total == 0:
            try:
                return Fraction(text)
            except Exception:
                return Fraction(1)
        return total

    def _format_quantity(self, quantity: Fraction) -> str:
        if quantity.denominator == 1:
            return str(quantity.numerator)
        return f"{quantity.numerator}/{quantity.denominator}"

    def _classify_item(self, item: str) -> str:
        if any(token in item for token in ["cheese", "milk", "butter", "yogurt", "cream"]):
            return "dairy"
        if any(token in item for token in ["onion", "garlic", "tomato", "lemon", "potato", "pepper", "lettuce", "spinach"]):
            return "produce"
        if any(token in item for token in ["bread", "flour", "pasta", "noodle", "baguette"]):
            return "bakery"
        if any(token in item for token in ["salt", "pepper", "cumin", "paprika", "oregano", "basil"]):
            return "spices"
        if any(token in item for token in ["chicken", "beef", "pork", "turkey", "tofu", "fish", "egg"]):
            return "protein"
        return "pantry"

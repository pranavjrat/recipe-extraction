#!/usr/bin/env python3
"""Quick test script to verify recipe extraction works"""

import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent
load_dotenv(project_root / ".env")

# Add backend to path
sys.path.insert(0, str(project_root / "backend"))

from app.extractor import RecipeExtractor

# Test with sample recipe text
SAMPLE_RECIPE = """
CHOCOLATE CHIP COOKIES

Prep Time: 15 minutes
Cook Time: 12 minutes
Servings: 24 cookies
Difficulty: Easy

INGREDIENTS:
- 2 cups all-purpose flour
- 1 cup butter, softened
- 3/4 cup sugar
- 3/4 cup brown sugar
- 2 large eggs
- 2 teaspoons vanilla extract
- 1 teaspoon salt
- 1 teaspoon baking soda
- 2 cups chocolate chips

INSTRUCTIONS:
1. Preheat oven to 375°F.
2. Cream butter and sugars until light and fluffy.
3. Beat in eggs one at a time, then add vanilla.
4. In another bowl, combine flour, salt, and baking soda.
5. Mix flour mixture into butter mixture.
6. Stir in chocolate chips.
7. Drop spoonfuls onto baking sheets.
8. Bake 9-12 minutes until golden.
9. Cool on sheets for 1 minute, then transfer to wire racks.
"""

if __name__ == "__main__":
    print("Testing Recipe Extraction...")
    print("=" * 60)
    
    try:
        extractor = RecipeExtractor()
        result = extractor.extract(
            url="http://test.local/recipe",
            raw_text=SAMPLE_RECIPE
        )
        
        print("\n✅ EXTRACTION SUCCESSFUL!\n")
        print(json.dumps(result, indent=2))
        
        # Validate required fields
        print("\n" + "=" * 60)
        print("VALIDATION REPORT:")
        print("=" * 60)
        
        checks = {
            "Title": result.get("title"),
            "Ingredients": len(result.get("ingredients", [])),
            "Instructions": len(result.get("instructions", [])),
            "Cuisine": result.get("cuisine"),
            "Prep Time": result.get("prep_time"),
            "Cook Time": result.get("cook_time"),
            "Servings": result.get("servings"),
            "Difficulty": result.get("difficulty"),
            "Nutrition": result.get("nutrition"),
            "Substitutions": len(result.get("substitutions", [])),
            "Shopping List": len(result.get("shopping_list", {})),
            "Related Recipes": len(result.get("related_recipes", [])),
        }
        
        for field, value in checks.items():
            status = "✅" if value else "⚠️"
            print(f"{status} {field}: {value}")
            
    except Exception as e:
        print(f"\n❌ EXTRACTION FAILED!")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

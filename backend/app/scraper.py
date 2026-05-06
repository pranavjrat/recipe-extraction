import requests
from bs4 import BeautifulSoup
from typing import Optional, Tuple


class RecipeScraper:
    """
    Fetches recipe pages and extracts structured data via JSON-LD or heuristics.
    
    Features:
    - HTTP scraping with browser-like headers to avoid blocks
    - 403 Forbidden recovery: visits homepage to establish cookies
    - JSON-LD extraction (schema.org recipe format)
    - Heuristic fallback for unstructured pages
    - Error handling for invalid URLs, blocked sites, network timeouts
    """
    def __init__(self):
        # Browser-like headers to avoid detection as bot
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.google.com/',
        }

    def fetch(self, url: str, timeout: int = 10) -> Tuple[str, Optional[str]]:
        """
        Fetch HTML from a recipe URL with error recovery.
        
        Args:
            url: Recipe page URL
            timeout: Request timeout in seconds (default 10)
        
        Returns:
            Tuple of (html_content, final_url after redirects)
        
        Raises:
            PermissionError: If site returns HTTP 403 (bot block) after recovery attempt
            requests.HTTPError: For other HTTP errors (404, 500, etc.)
            requests.Timeout: If fetch exceeds timeout (network issue)
            requests.RequestException: For other network/connection errors
        """
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            resp = session.get(url, timeout=timeout)
        except requests.Timeout:
            raise TimeoutError(f"Request timed out after {timeout}s for {url}")
        except requests.RequestException as e:
            raise requests.RequestException(f"Network error fetching {url}: {e}")

        # HTTP 403: Bot blocked. Try homepage visit to establish cookies.
        if resp.status_code == 403:
            try:
                # Extract domain and visit homepage
                parsed = requests.utils.urlparse(url)
                homepage = f"{parsed.scheme}://{parsed.netloc}/"
                session.get(homepage, timeout=timeout)  # Establish session
                # Retry original URL
                resp = session.get(url, timeout=timeout)
            except Exception:
                # Homepage visit failed; skip recovery
                pass

        # Still blocked after recovery
        if resp.status_code == 403:
            raise PermissionError(
                f"The site blocked automated access with HTTP 403 for {url}. "
                "Try a different recipe site or provide raw recipe text/HTML."
            )

        # Other HTTP errors (404, 500, etc.)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise requests.HTTPError(f"HTTP {resp.status_code} for {url}: {e}")

        return resp.text, resp.url

    def extract_json_ld(self, html: str) -> Optional[dict]:
        """
        Extract Recipe data from JSON-LD structured data in <script> tags.
        
        Follows schema.org specification for Recipe type.
        JSON-LD is the most reliable data source: clean, machine-readable,
        and designed specifically for recipe sites.
        
        Args:
            html: HTML content of page
        
        Returns:
            Dict with recipe data, or None if no JSON-LD recipe found.
        
        Error handling:
        - Handles malformed JSON gracefully (logs, continues to next script)
        - Checks for both single recipe objects and arrays
        - Verifies @type field matches 'recipe' (case-insensitive)
        """
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                # Handle both single object and array of objects
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type', '').lower() == 'recipe':
                            return item
                elif isinstance(data, dict) and data.get('@type', '').lower() == 'recipe':
                    return data
            except (json.JSONDecodeError, AttributeError, TypeError):
                # Malformed JSON or invalid script; skip to next
                continue
        return None

    def heuristic_extract(self, html: str) -> dict:
        """
        Fallback extraction for pages without JSON-LD structured data.
        
        Strategy:
        1. Title: h1 tag (primary), h2 if needed
        2. Ingredients: Look for <ul>/<ol> with 'ingredient' class, then scan all <li> for unit keywords
        3. Instructions: Look for <ol>/<ul> with 'instruction/direction/steps' class, then scan <p> tags for cooking verbs
        
        Args:
            html: HTML content
        
        Returns:
            Dict with title, ingredients (list of strings), instructions (list of strings).
            Empty lists if fields not found.
        
        Error handling:
        - Gracefully handles missing/malformed HTML elements
        - Filters short/irrelevant text snippets
        - Searches for common class naming conventions
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title from h1 tag
        title_tag = soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else None

        # Extract ingredients: prioritize marked lists, fall back to keyword scan
        ingredients = []
        for cls in ['ingredient', 'ingredients', 'recipe-ingredients']:
            for ul in soup.find_all(['ul', 'ol'], class_=lambda x: x and cls in x.lower()):
                for li in ul.find_all('li'):
                    txt = li.get_text().strip()
                    if txt:
                        ingredients.append(txt)
        # Fallback: scan all li tags for those containing unit keywords
        if not ingredients:
            for li in soup.find_all('li'):
                txt = li.get_text().strip()
                # Heuristic: ingredient li tags usually contain quantity units
                if any(tok in txt.lower() for tok in ['cup', 'tbsp', 'tsp', 'slice', 'ounce', 'oz', 'g', 'kg', 'ml']):
                    ingredients.append(txt)

        # Extract instructions: prioritize marked lists, fall back to paragraph scan
        instructions = []
        for cls in ['instruction', 'instructions', 'direction', 'directions', 'method', 'steps']:
            for ol in soup.find_all(['ol', 'ul'], class_=lambda x: x and cls in x.lower()):
                for li in ol.find_all('li'):
                    txt = li.get_text().strip()
                    if txt:
                        instructions.append(txt)
        # Fallback: scan paragraphs for those containing cooking verbs
        if not instructions:
            for p in soup.find_all('p'):
                txt = p.get_text().strip()
                # Heuristic: instruction paragraphs are typically 5+ words and contain cooking verbs
                if txt and len(txt.split()) > 5 and any(word in txt.lower() for word in ['mix', 'bake', 'cook', 'heat', 'stir', 'add', 'pour']):
                    instructions.append(txt)

        return {
            'title': title,
            'ingredients': ingredients,
            'instructions': instructions
        }

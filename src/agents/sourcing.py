"""
SourcingAgent
=============
Hit SerpAPI with construction‑×‑AI keyword bundles and yield raw candidates
(domain, snippet, link).  Designed to be called *asynchronously* from LangGraph.
"""

from __future__ import annotations
import asyncio, os, re, logging
from pathlib import Path
from serpapi import GoogleSearch
from typing import AsyncIterator, Dict, List

SERP_KEY = os.getenv("SERPAPI_API_KEY")
PROJECT_DIR = Path(__file__).resolve().parents[2]
KEYWORD_FILE = PROJECT_DIR / "keywords.csv"

logger = logging.getLogger(__name__)


def _load_queries() -> List[str]:
    """Read newline‑delimited queries from keywords.csv"""
    if not KEYWORD_FILE.exists():
        raise FileNotFoundError(f"{KEYWORD_FILE} missing")
    lines = [l.strip() for l in KEYWORD_FILE.read_text().splitlines() if l.strip()]
    return lines

# ------------------------------------
# NEW: read domains from seeds.csv
SEED_FILE = PROJECT_DIR / "seeds.csv"
if SEED_FILE.exists():
    SEEDS = {d.strip() for d in SEED_FILE.read_text().splitlines() if d.strip()}
else:
    SEEDS = set()
# ------------------------------------


async def _serp_request(query: str, num: int = 10) -> List[Dict]:
    params = {"q": query, "api_key": SERP_KEY, "num": num}
    search = GoogleSearch(params)
    data = search.get_dict()
    return data.get("organic_results", [])


async def fetch_results() -> AsyncIterator[Dict]:
    """Async generator of {domain, snippet, link, query} dicts."""

     # ➊  first, emit seed domains so they always reach the classifier
    for domain in SEEDS:
        yield {
            "query": "seed",            # label so you know where it came from
            "domain": domain,
            "snippet": "",
            "link": f"https://{domain}",
        }

    # ➋  then do the normal SerpAPI hits
    queries = _load_queries()
    for q in queries:
        try:
            results = await _serp_request(q)
        except Exception as exc:
            logger.warning("SerpAPI fail on %s → %s", q, exc)
            continue
        for res in results:
            link = res.get("link") or ""
            match = re.match(r"https?://(?:www\.)?([^/]+)/?", link)
            if not match:
                continue
            domain = match.group(1).lower()
            yield {
                "query": q,
                "domain": domain,
                "snippet": res.get("snippet", ""),
                "link": link,
            }


# ---- LangGraph node entry‑point ------------------------------------------ #
async def run(state: dict | None = None, **kwargs):
    """Return list of raw candidates.  LangGraph passes state (ignored here)."""
    if not SERP_KEY:
        logger.warning("No SERPAPI_API_KEY found, using seeds.csv only")
        return [{
            "query": "seed",
            "domain": domain,
            "snippet": "",
            "link": f"https://{domain}",
        } for domain in SEEDS]
    
    return [item async for item in fetch_results()]

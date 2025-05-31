"""
ClassifierAgent
===============
Take raw candidate dicts from SourcingAgent, decide if they live at the
intersection of *construction* AND *AI/ML*.  On a positive hit, persist to
SQLite + Chroma vector store.
"""

from __future__ import annotations
import os, re, asyncio, logging
from typing import List, Dict

import openai, httpx
from bs4 import BeautifulSoup

from src.db import Session, Company
from src.vector import embed, embed_async, upsert_company

openai.api_key = os.getenv("OPENAI_API_KEY")
logger = logging.getLogger(__name__)

# crude keyword bags (you can refine later)
CONSTRUCTION_KWS = {
    "construction",
    "bim",
    "rfi",
    "site",
    "jobsite",
    "punchlist",
    "safety",
    "billing",
    "subcontractor",
    "draw",
}
AI_KWS = {
    "ai",
    "machine learning",
    "ml",
    "computer vision",
    "deep learning",
    "llm",
    "chatbot",
    "autonomous",
    "agent",
    "ai-powered",
    "SaaS",
    "AI-powered",
    "AI-enabled",
    "AI-driven",
    "AI-enabled",
    "AI-powered",
}


async def _fetch_home(domain: str) -> str | None:
    """Grab <meta description> or first 1 kB of homepage text."""
    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
            r = await client.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
    except Exception as exc:
        logger.debug("fetch fail %s → %s", domain, exc)
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    desc = soup.find("meta", attrs={"name": "description"})
    if desc and desc.get("content"):
        return desc["content"]
    # fallback: first <p>
    p = soup.find("p")
    return p.get_text(strip=True)[:1024] if p else None


def _is_relevant(text: str) -> bool:
    """Check if text contains any AI-related keywords."""
    low = text.lower()
#    c_hit = any(k in low for k in CONSTRUCTION_KWS)
#    a_hit = any(k in low for k in AI_KWS)
    a_hit = any(k in low for k in AI_KWS | CONSTRUCTION_KWS)
    if a_hit:
        logger.debug("Found AI keywords in text")
    return a_hit


async def classify_batch(raw_items: List[Dict]) -> List[Dict]:
    out: List[Dict] = []
    total = len(raw_items)
    logger.info(f"Starting to classify {total} companies...")
    
    for i, item in enumerate(raw_items, 1):
        domain = item["domain"]
        logger.info(f"Processing {i}/{total}: {domain}")
        
        # duplicate check
        with Session() as ses:
            if ses.query(Company).filter_by(domain=domain).first():
                logger.info(f"Skipping {domain} - already in database")
                continue
                
        # scrape
        logger.info(f"Fetching homepage for {domain}")
#        home_txt = await _fetch_home(domain)
        home_txt = await _fetch_home(domain) or ""
        candidate_text = (item["snippet"] or "") + "  " + home_txt
        if not home_txt:
            logger.info(f"No homepage text found for {domain}")
            continue
            
#        if not _is_relevant(home_txt):
        if not _is_relevant(candidate_text):
            logger.info(f"No AI keywords found for {domain}")
            continue  # toss out
            
        # save
        logger.info(f"Saving {domain} to database")
        try:
            with Session() as ses:
                c = Company(name=domain.split(".")[0].title(), domain=domain, description=home_txt)
                ses.add(c)
                ses.commit()
                ses.refresh(c)
                try:
                    upsert_company(c.id, home_txt)
                    out.append({"company_id": c.id, "domain": domain})
                    logger.info("✅ kept %s", domain)
                except Exception as exc:
                    logger.error(f"Failed to upsert to vector DB for {domain}: {exc}")
                    # Continue even if vector DB fails
                    out.append({"company_id": c.id, "domain": domain})
                    logger.info("✅ kept %s (without vector DB)", domain)
        except Exception as exc:
            logger.error(f"Failed to save {domain} to database: {exc}")
            continue
            
    logger.info(f"Classification complete. Kept {len(out)} out of {total} companies")
    return out


# ---- LangGraph node ------------------------------------------------------ #
async def run(state: List[Dict], **kwargs):
    """state == list of raw dicts from sourcing.run"""
    return await classify_batch(state)

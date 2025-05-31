from __future__ import annotations
import asyncio, logging
from typing import Dict, List

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.exc import IntegrityError

from src.db import Session, Company
from src.vector import embed_and_upsert

logger = logging.getLogger(__name__)

CONSTRUCTION_KWS = {
    "construction", "bim", "jobsite", "rfi", "safety",
    "contractor", "prefab", "design-build", "subcontractor",
    "site", "punchlist", "billing", "draw", "scheduleing",
    "project", "project management", "procurement", "construction management",
    }       # keep as before

AI_KWS           = {"ai", "machine learning", "ml", "deep learning",
    "computer vision", "analytics", "predictive", "llm", "chatbot", "smart",
    "autonomous", "agent", "ai-powered", "SaaS","AI-enabled", "AI-driven",
    }

UA = {"User-Agent": "Mozilla/5.0 Chrome/124"}
HTTP_TIMEOUT = httpx.Timeout(10)

async def _fetch_home(domain: str) -> str | None:
    """Fetch homepage text from a domain."""
    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as c:
            try:
                r = await c.get(url, headers=UA)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for {domain}: {e}")
                return None
            except httpx.RequestError as e:
                logger.warning(f"Request error for {domain}: {e}")
                return None
            except Exception as e:
                logger.warning(f"Unexpected error for {domain}: {e}")
                return None

            try:
                soup = BeautifulSoup(r.text, "html.parser")
                # Try meta description first
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    return meta["content"][:1024]
                
                # Try first paragraph
                p = soup.find("p")
                if p:
                    return p.get_text(strip=True)[:1024]
                
                # Try body text as last resort
                body = soup.find("body")
                if body:
                    return body.get_text(strip=True)[:1024]
                
                return None
            except Exception as e:
                logger.warning(f"Failed to parse {domain}: {e}")
                return None
    except Exception as e:
        logger.warning(f"Failed to fetch {domain}: {e}")
        return None

def _is_relevant(t: str) -> bool:
    t = t.lower()
    return any(k in t for k in AI_KWS | CONSTRUCTION_KWS)

# ------------- LangGraph node -----------------
async def run(candidates: List[Dict], **_) -> List[Dict]:
    """
    candidates: list of dicts from sourcing.run
    returns   : list of {'company_id': int, 'domain': str}
    """
    if not candidates:
        return []

    logger.info("Starting to classify %d companies…", len(candidates))
    sem = asyncio.Semaphore(8)             # NEW: local to this event-loop
    out: list[Dict] = []

    async def handle(item, idx):
        try:
            dom = item["domain"]
            logger.info("🔍  (%d/%d) %s", idx, len(candidates), dom)

            async with sem:                   # limit concurrent fetch
                try:
                    home = await asyncio.wait_for(_fetch_home(dom), timeout=30) or ""
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching {dom}")
                    return
                except Exception as e:
                    logger.error(f"Error fetching {dom}: {e}")
                    return

            text = (item.get("snippet") or "") + "  " + home

            if not _is_relevant(text):
                logger.info("❌ rejected %s - no relevant keywords", dom)
                return

            # DB insert / get
            try:
                with Session() as ses:
                    comp = Company(name=dom.split(".")[0].title(),
                               domain=dom, description=home)
                    try:
                        ses.add(comp)
                        ses.commit()
                        ses.refresh(comp)
                    except IntegrityError:
                        ses.rollback()
                        comp = ses.query(Company).filter_by(domain=dom).first()
                        if not comp:
                            logger.error("Failed to get existing company %s", dom)
                            return

                # vector store (may hit OpenAI)
                ''' 
                try:
                    logger.info(f"Starting embedding process for {dom}")
                    async with sem:
                        logger.info(f"Calling embed_and_upsert for {dom} with ID {comp.id}")
                        await asyncio.wait_for(embed_and_upsert(comp.id, text), timeout=30)
                    logger.info(f"Successfully completed embedding for {dom}")
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout embedding {dom}")
                except Exception as e:
                    logger.error(f"Failed to embed {dom}: {str(e)}")
                    # Continue even if embedding fails
                    pass
                '''
                await embed_and_upsert(comp.id, text)  # let it crash visibly the first time

                
                logger.info("✅ kept %s", dom)
                out.append({"company_id": comp.id, "domain": dom})
            except Exception as e:
                logger.error(f"Failed to process {dom}: {str(e)}")
                return
        except Exception as e:
            logger.error(f"Unexpected error processing {item.get('domain', 'unknown')}: {str(e)}")
            return

    # Create tasks with proper error handling
    tasks = []
    for i, item in enumerate(candidates, 1):
        task = asyncio.create_task(handle(item, i))
        tasks.append(task)

    # Wait for all tasks with timeout
    try:
        await asyncio.wait(tasks, timeout=300)  # 5 minute overall timeout
    except asyncio.TimeoutError:
        logger.error("Overall classification timeout reached")
    except Exception as e:
        logger.error("Error in gather: %s", str(e))

    # Cancel any remaining tasks
    for task in tasks:
        if not task.done():
            task.cancel()

    logger.info("Classifier done – %d/%d accepted", len(out), len(candidates))
    return out

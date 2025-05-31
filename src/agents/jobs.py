"""
JobAgent
========
Detect a company's job board provider (Greenhouse, Lever, Workday) and store
relevant DS/ML openings into SQLite.
"""

from __future__ import annotations
import asyncio, logging, re, httpx, json, datetime
import time
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from src.db import Session, Company, Job

logger = logging.getLogger(__name__)
TITLE_RE = re.compile(
    r"\b(Data|Machine Learning|Manager|Project Manager|Computer Vision|Deep Learning|AI|ML|LLM|Analytics|Engineer|Scientist|Developer|Analyst|Designer|Programmer|Developer|Software Engineer|Data Scientist|Data Analyst|Data Engineer)\b",
    re.I,
)

CAREERS_PATHS = [
    "/careers", "/jobs", "/careers-legal-tech-industry", "/company/careers",
    "/en-us/about-nvidia/careers", "/about/careers", "/join-us", "/work-with-us",
        # -- new suggestions --
    "/career", "/positions", "/vacancies", "/open-positions", "/current-openings",
    "/life-at", "/team/join", "/about-us/careers", "/company/jobs",
    "/workhere", "/apply", "/en/careers", "/careers.html",
    "/career-center", "/talent", "/employment", "/careers#jobs",
]

async def _detect_board(domain: str) -> Dict | None:
    """Return dict {'type': 'greenhouse', 'slug': 'company'} or similar."""
    base_url = f"https://{domain}"

    for path in CAREERS_PATHS:
        url = urljoin(base_url, path)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(url, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            # Greenhouse
            gh = re.search(r"boards\.greenhouse\.io\/([\w\-]+)", r.text)
            if gh:
                return {"type": "greenhouse", "slug": gh.group(1)}
            # Lever
            lv = re.search(r"jobs\.lever\.co\/([\w\-]+)", r.text)
            if lv:
                return {"type": "lever", "slug": lv.group(1)}
            # Workday
            wd = re.search(r"myworkdayjobs\.com\/([\w\-]+)/([\w\-]+)", r.text)
            if wd:
                return {"type": "workday", "path": wd.group(0)}
            # Try direct parse
            if "career" in url.lower() or "job" in url.lower():
                return {"type": "direct", "url": url}
        except Exception as exc:
            logger.debug(f"Failed to fetch {url}: {exc}")
            continue

    return {"type": "direct", "url": f"https://{domain}"}

async def _fetch_greenhouse(board_slug: str) -> List[Dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_slug}/jobs"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        if "jobs" not in data:
            logger.warning(f"No jobs found for board {board_slug}")
            return []
        return [
            {"title": j["title"], "location": j["location"]["name"], "url": j["absolute_url"]}
            for j in data["jobs"]
        ]
    except Exception as exc:
        logger.error(f"Failed to fetch jobs from Greenhouse for board {board_slug}: {exc}")
        return []

async def _fetch_lever(slug: str) -> List[Dict]:
    url = f"https://api.lever.co/v1/postings/{slug}?mode=json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        return [
            {
                "title": j["text"],
                "location": j.get("categories", {}).get("location") or "Unknown",
                "url": j["hostedUrl"],
            }
            for j in data
        ]
    except Exception as exc:
        logger.error(f"Failed to fetch jobs from Lever for {slug}: {exc}")
        return []

async def _fetch_workday(path: str) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"https://{path}")
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        outs = []
        for a in soup.select("a[data-automation-id='jobPostingLink']"):
            outs.append({
                "title": a.get_text(strip=True),
                "location": "Workday",
                "url": "https://" + path.split("/")[0] + a["href"],
            })
        return outs
    except Exception as exc:
        logger.error(f"Failed to fetch jobs from Workday for {path}: {exc}")
        return []

async def _fetch_direct(url: str) -> List[Dict]:
    """Fetch jobs directly from a careers page."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        outs = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text or not any(kw in text.lower() for kw in ["job", "career", "position", "opening"]):
                continue
            if not href.startswith(("http://", "https://")):
                href = urljoin(url, href)
            outs.append({
                "title": text,
                "location": "Unknown",
                "url": href,
            })
        return outs
    except Exception as exc:
        logger.error(f"Failed to fetch jobs directly from {url}: {exc}")
        return []

async def harvest_jobs(company_id: int):
    with Session() as ses:
        comp = ses.get(Company, company_id)
        board = await _detect_board(comp.domain)
        if not board:
            logger.debug(f"No job board found for {comp.domain}")
            return

        if board["type"] == "greenhouse":
            jobs = await _fetch_greenhouse(board["slug"])
        elif board["type"] == "lever":
            jobs = await _fetch_lever(board["slug"])
        elif board["type"] == "workday":
            jobs = await _fetch_workday(board["path"])
        elif board["type"] == "direct":
            jobs = await _fetch_direct(board["url"])
        else:
            jobs = []

        added = 0
        for j in jobs:
            if not TITLE_RE.search(j["title"]):
                continue
            if ses.query(Job).filter_by(url=j["url"]).first():
                continue
            job = Job(
                company_id=company_id,
                title=j["title"],
                location=j["location"],
                posting_date=datetime.date.today(),  # Workday & Lever omit dates
                description="",
                url=j["url"],
                remote=bool(re.search(r"Remote|Anywhere", j["location"], re.I)),
            )
            ses.add(job)
            added += 1
        ses.commit()
        if added:
            logger.info("➕ added %s ML jobs for %s", added, comp.domain)

async def harvest_jobs_limited(company_id, semaphore):
    print(f"[{time.strftime('%X')}] WAITING: company_id={company_id}")
    async with semaphore:
        print(f"[{time.strftime('%X')}] START:   company_id={company_id}")
        try:
            await harvest_jobs(company_id)
            print(f"[{time.strftime('%X')}] DONE:    company_id={company_id}")
        except Exception as e:
            print(f"[{time.strftime('%X')}] ERROR:   company_id={company_id} - {e}")
    print(f"[{time.strftime('%X')}] EXIT:    company_id={company_id}")

# ---- LangGraph node ------------------------------------------------------ #
async def run(state, **kwargs):
    """Process jobs for classified companies."""
    # Handle both list and dict state formats
    if isinstance(state, list):
        classified = state
    else:
        classified = state.get("classified", [])

    if not classified:
        logger.info("No classified companies to process jobs for")
        return state

    logger.info("Starting to process jobs for %d companies...", len(classified))

    # Semaphore is created **here** on the right event loop
    semaphore = asyncio.Semaphore(5)

    await asyncio.gather(*(harvest_jobs_limited(item["company_id"], semaphore) for item in classified))

    # Update state with processed companies Ensure output is always a dict!
    if isinstance(state, dict):
        state["jobs_processed"] = classified
        return state
    else:
        # If input was a list, wrap as dict
        return {"classified": classified, "jobs_processed": classified}

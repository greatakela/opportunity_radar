"""
NotifierAgent
=============
For solo use: dump today's ≥70‑score jobs to a CSV under `digests/`.
"""

from __future__ import annotations
import datetime, logging, pathlib, os
import pandas as pd
from sqlalchemy import text
from src.db import Session

logger = logging.getLogger(__name__)

THRESH = int(os.getenv("DIGEST_THRESHOLD", "20"))   # default 20 during testing

def _has_hot_jobs() -> bool:
    with Session() as ses:
        n = ses.execute(text("SELECT count(*) FROM job WHERE score>=:t"), {"t": THRESH}).scalar()
        return n and n > 0

async def run(state, **kwargs):
    """Create digest file for high-scoring jobs."""

    # Defensive: Accept both dict and list, always work with dict.
    if isinstance(state, dict):
        jobs_processed = state.get("jobs_processed", [])
    elif isinstance(state, list):
        # Log warning, convert to dict.
        logger.warning("State received as list, not dict. Wrapping as dict for consistency.")
        jobs_processed = state
        state = {"jobs_processed": jobs_processed}
    else:
        logger.error(f"Unknown state type: {type(state)}")
        jobs_processed = []
        state = {"jobs_processed": jobs_processed}

    if not jobs_processed:
        logger.info("No processed jobs to create digest for")
        return state

    logger.info("Creating digest for processed jobs...")

    # Get high-scoring jobs
    with Session() as ses:
        jobs = ses.execute(text("""
            SELECT j.*, c.name as company_name, c.domain
            FROM job j
            JOIN company c ON j.company_id = c.id
            WHERE j.score >= :threshold
            ORDER BY j.score DESC
        """), {"threshold": THRESH}).fetchall()

        if not jobs:
            logger.info("No jobs above threshold %d", THRESH)
            state["digest_created"] = False
            return state

        # Create digest directory if it doesn't exist
        digest_dir = pathlib.Path("digests")
        digest_dir.mkdir(exist_ok=True)

        # Create digest file
        today = datetime.date.today()
        digest_file = digest_dir / f"digest_{today}.csv"

        # Convert to DataFrame and save
        df = pd.DataFrame(jobs)
        df.to_csv(digest_file, index=False)
        logger.info("Created digest file: %s", digest_file)

        # Update state
        state["digest_created"] = True
        state["digest_file"] = str(digest_file)
        return state

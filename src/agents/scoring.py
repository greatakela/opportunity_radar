"""
ScoringAgent
============
Attach a fit_score (0‑100) to each new Job row, based on the rubric weights
we discussed.  For brevity, employee_count and funding_stage are bucketised to
ranges instead of calling extra APIs.
"""

from __future__ import annotations
import os, logging
from typing import Dict

import openai
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db import Session, Job, Company
from src.vector import embed

openai.api_key = os.getenv("OPENAI_API_KEY")
logger = logging.getLogger(__name__)

WEIGHTS = {
    "skill_similarity": 0.37,
    "ai_depth": 0.28,
#    "funding_stage": 0.15,
    "remote": 0.15,
    "construction_relevance": 0.10,
    "growth_velocity": 0.10,  # placeholder‑static
}


def _funding_bucket(stage: str | None) -> float:
    if not stage:
        return 0.2
    stage = stage.lower()
    if "seed" in stage or "angel" in stage:
        return 0.2
    if "series a" in stage:
        return 0.4
    if "series b" in stage:
        return 0.6
    if "series c" in stage:
        return 0.8
    return 1.0  # series d+ or ipo


def _ai_depth(title: str) -> float:
    if any(k in title.lower() for k in ["computer vision", "deep learning", "llm"]):
        return 1.0
    if any(k in title.lower() for k in ["machine learning", "data scientist"]):
        return 0.8
    return 0.5


def _construction_relevance(comp_desc: str) -> float:
    hits = sum(comp_desc.lower().count(k) for k in ["bim", "construction", "jobsite", "scheduleing", "project management", "procurement", "construction management"])
    return min(hits / 3, 1.0)


def _similarity(resume_emb: list[float], text: str) -> float:
    import numpy as np

    emb = embed(text)
    return float(np.dot(emb, resume_emb) / (np.linalg.norm(emb) * np.linalg.norm(resume_emb)))


# cache resume embedding once
with open("resume.txt", "r", encoding="utf‑8") as fh:
    RESUME_EMB = embed(fh.read())


def score_job(job: Job, company: Company) -> float:
    feats = {
        "skill_similarity": _similarity(RESUME_EMB, job.title + " " + job.description),
        "ai_depth": _ai_depth(job.title),
        "funding_stage": _funding_bucket(company.funding_stage),
        "remote": 1.0 if job.remote else 0.0,
        "construction_relevance": _construction_relevance(company.description or ""),
        "growth_velocity": 0.5,  # TODO: implement
    }
    return sum(feats[k] * w for k, w in WEIGHTS.items()) * 100.0


async def run(state: list[dict], **kwargs):
    """Score newly inserted jobs that don't have a score yet."""
    try:
        with Session() as ses:
            q = (
                ses.query(Job)
                .options(joinedload(Job.company))
                .filter(Job.score == None)  # newly inserted jobs
            )
            jobs = q.all()
            logger.info(f"Found {len(jobs)} jobs to score")
            
            for job in jobs:
                try:
                    job.score = score_job(job, job.company)
                    logger.info(f"Scored job {job.title} with score {job.score}")
                except Exception as exc:
                    logger.error(f"Failed to score job {job.title}: {exc}")
                    continue
                    
            ses.commit()
            logger.info("Successfully scored all jobs")
    except Exception as exc:
        logger.error(f"Error in scoring.run: {exc}")
        raise
        
    return state  # passes unchanged so notifier can act

"""
EnrichmentAgent (People Data Labs edition)
-----------------------------------------
PDL docs: https://docs.peopledatalabs.com/docs/company-enrichment-api
"""

from __future__ import annotations
import os, asyncio, httpx, logging
from src.db import Session, Company

PDL_KEY   = os.getenv("PDL_API_KEY")
PDL_URL   = "https://api.peopledatalabs.com/v5/company/enrich"
HEADERS   = {"X-Api-Key": PDL_KEY}
logger    = logging.getLogger(__name__)

import json

async def enrich_one(company_id: int):
    with Session() as ses:
        comp = ses.get(Company, company_id)
        if not comp or comp.employees:              # already done
            return

    params = {"website": comp.domain}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(PDL_URL, headers=HEADERS, params=params)
        if r.status_code == 404:
            return                                  # no match
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.warning("PDL fail %s → %s", comp.domain, exc)
        return

    with Session() as ses:
        c = ses.get(Company, company_id)
        # Convert headquarters to JSON string
        c.headquarters = json.dumps(data.get("location"))
        size_data = data.get("size")
        if isinstance(size_data, dict):
            c.employees = size_data.get("value")
        else:
            c.employees = None
        c.funding_stage = data.get("founded")                        # use founding year as proxy
        ses.commit()
        logger.info("🟢 PDL enriched %s", c.domain)

async def run(state, **kwargs):
    await asyncio.gather(*(enrich_one(i["company_id"]) for i in state))
    return state

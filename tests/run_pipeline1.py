"""
Run the complete opportunity radar pipeline:
1. Source companies
2. Classify and filter them
3. Enrich company data
4. Find jobs
5. Score jobs
6. Create notification digest
"""

import asyncio
import logging
from src.agents import sourcing, classifier, enrichment, jobs, scoring, notifier
from src.db import Session, Company
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting pipeline...")
    
    # 1. Source companies
    logger.info("Step 1: Sourcing companies...")
    state = await sourcing.run()
    logger.info(f"Found {len(state)} potential companies")
    logger.info("Sample domains: %s", [item['domain'] for item in state[:3]])
    
    # 2. Classify and filter
    logger.info("Step 2: Classifying companies...")
    state = await classifier.run(state)
    logger.info(f"Kept {len(state)} relevant companies")
    if state:
        logger.info("Kept domains: %s", [item['domain'] for item in state])
    else:
        logger.warning("No companies passed the classifier! Check if they have both construction AND AI keywords")
        return
    
    # 3. Enrich company data
    logger.info("Step 3: Enriching company data...")
    state = await enrichment.run(state)
    
    # 4. Find jobs
    logger.info("Step 4: Finding jobs...")
    state = await jobs.run(state)
    
    # 5. Score jobs
    logger.info("Step 5: Scoring jobs...")
    state = await scoring.run(state)
    
    # 6. Create notification digest
    logger.info("Step 6: Creating notification digest...")
    state = await notifier.run(state)
    
    # Final check
    with Session() as ses:
        company_count = ses.execute(text("SELECT COUNT(*) FROM company")).scalar()
        job_count = ses.execute(text("SELECT COUNT(*) FROM job")).scalar()
        logger.info(f"Final database state: {company_count} companies, {job_count} jobs")
    
    logger.info("Pipeline completed!")

if __name__ == "__main__":
    asyncio.run(main()) 
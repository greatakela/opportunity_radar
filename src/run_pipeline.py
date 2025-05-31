"""
Run the opportunity radar pipeline.
"""

import asyncio
import logging
from typing import Dict, List

from src.agents.sourcing import run as source
from src.agents.classifier import run as classify
from src.agents.jobs import run as process_jobs
from src.agents.notifier import run as notify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_pipeline():
    """Run the full pipeline."""
    # Initialize state
    state = {}
    
    # Source companies
    logger.info("Starting sourcing...")
    state = await source(state)
    
    # Classify companies
    logger.info("Starting classification...")
    state = await classify(state)
    
    # Process jobs
    logger.info("Starting job processing...")
    state = await process_jobs(state)
    
    # Create digest
    logger.info("Creating digest...")
    state = await notify(state)
    
    logger.info("Pipeline complete!")
    return state

if __name__ == "__main__":
    asyncio.run(run_pipeline()) 
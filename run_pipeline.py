import logging
import json
import sys
import traceback
import os
from src.graph import run_once

log_file = "output.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w', encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
    force=True  # Overwrites previous config; Python 3.8+
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting pipeline...")
    try:
        result = run_once()
        logger.info("Pipeline completed!")
 
        with open("final_state.json", "w", encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        logger.info("Saved final pipeline state to final_state.json")
        logger.info(f"Log output written to {os.path.abspath(log_file)}")
        return result
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        logger.error(traceback.format_exc())
        raise

if __name__ == "__main__":
    main()

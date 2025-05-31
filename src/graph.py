"""
src/graph.py  ·  LangGraph 0.4 API
----------------------------------
Wires the six agents into a linear pipeline:

source → classify → enrich → jobs → score → notify
"""

from __future__ import annotations
import os, logging, sys, asyncio
from pathlib import Path
from dotenv import load_dotenv

# ── 0. environment & logging ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]

# Force reload environment variables
env_path = ROOT / ".env"
if env_path.exists():
    # Clear any existing environment variables we want to reload
    if "LANGSMITH_ENDPOINT" in os.environ:
        del os.environ["LANGSMITH_ENDPOINT"]
    if "LANGSMITH_API_KEY" in os.environ:
        del os.environ["LANGSMITH_API_KEY"]
    if "LANGSMITH_PROJECT" in os.environ:
        del os.environ["LANGSMITH_PROJECT"]
    
    # Load fresh values from .env
    load_dotenv(env_path, override=True)  # vars: OPENAI_API_KEY, LANGSMITH_*, …

logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("graph")

# ── 1. langgraph 0.4 import ───────────────────────────────────────────────
from langgraph.graph import StateGraph   # replaces langgraph.Graph (0.3 and below)
from langsmith import Client
from langsmith.run_helpers import traceable

# ── 2. agents ─────────────────────────────────────────────────────────────
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents import (
    sourcing,
    classifier,
    enrichment,
    jobs,
    scoring,
    notifier,
)

# ── 3. build graph ────────────────────────────────────────────────────────
try:
    # Configure LangSmith client with proper endpoint
    api_url = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    if api_url:
        # Remove any comments, spaces, and ensure proper URL format
        api_url = api_url.split("#")[0]  # Remove comments
        api_url = "".join(api_url.split())  # Remove all whitespace
        if not api_url.startswith("http"):
            api_url = f"https://{api_url}"  # Ensure https prefix
    api_key = os.getenv("LANGSMITH_API_KEY")
    project_name = os.getenv("LANGSMITH_PROJECT", "opportunity_radar")
    
    logger.info(f"Initializing LangSmith client with URL: {api_url}")
    if not api_key:
        raise ValueError("LANGSMITH_API_KEY environment variable is not set")
    
    client = Client(
        api_url=api_url,
        api_key=api_key
    )
    TRACING_ENABLED = True
except Exception as e:
    logger.warning(f"Failed to initialize LangSmith client: {str(e)}")
    logger.debug("LangSmith configuration - URL: %s, API Key present: %s", 
                api_url, "Yes" if api_key else "No")
    client = None
    TRACING_ENABLED = False

g = StateGraph(dict)   # name shows up in LangSmith

# register nodes with proper run names and tags
if TRACING_ENABLED:
    g.add_node("source", traceable(sourcing.run, client=client, name="source_companies", tags=["pipeline", "source"]))
    g.add_node("classify", traceable(classifier.run, client=client, name="classify_companies", tags=["pipeline", "classify"]))
    #g.add_node("enrich", traceable(enrichment.run, client=client, name="enrich_companies", tags=["pipeline", "enrich"]))
    g.add_node("jobs", traceable(jobs.run, client=client, name="find_jobs", tags=["pipeline", "jobs"]))
    g.add_node("score", traceable(scoring.run, client=client, name="score_jobs", tags=["pipeline", "score"]))
    g.add_node("notify", traceable(notifier.run, client=client, name="notify_jobs", tags=["pipeline", "notify"]))
else:
    g.add_node("source", sourcing.run)
    g.add_node("classify", classifier.run)
    #g.add_node("enrich", enrichment.run)
    g.add_node("jobs", jobs.run)
    g.add_node("score", scoring.run)
    g.add_node("notify", notifier.run)

# linear edges
g.add_edge("source", "classify")
#g.add_edge("classify", "enrich")
#g.add_edge("enrich", "jobs")
# pass straight to jobs
g.add_edge("classify", "jobs")
g.add_edge("jobs", "score")
g.add_edge("score", "notify")

# mark "notify" as a terminal state so invoke() returns after that node
g.set_entry_point("source")
g.set_finish_point("notify")

graph = g.compile()  

# ── 4. entry‑point helpers ────────────────────────────────────────────────
def run_once(input_query_file: str | None = None):
    """
    Execute the pipeline synchronously once.
    Pass a different keywords file via `input_query_file` if desired.
    """
    logger.info("🚀  starting Opportunity Radar run")
    if TRACING_ENABLED:
        try:
            run = client.create_run(
                project_name=project_name,
                name="opportunity_radar_pipeline",
                tags=["pipeline", "full_run"],
                inputs={"input_query_file": input_query_file},
                run_type="chain"
            )
            if run is None:
                logger.warning("Failed to create LangSmith run, continuing without tracing")
                result = asyncio.run(graph.ainvoke({"input_query_file": input_query_file}))
            else:
                try:
                    result = asyncio.run(graph.ainvoke({"input_query_file": input_query_file}))
    #                client.update_run(run.id, outputs=result)
                    # ── NEW: explicit successful close ──
                    run.end(outputs={"result": result}) 
                    return result   
                except Exception as e:
    #                client.update_run(run.id, error=str(e))
                    # ── NEW: explicit error close ──
                    run.end(error=str(e))
                    logger.error(f"Pipeline execution failed: {e}")               
                    raise
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith run: {e}")
            result = asyncio.run(graph.ainvoke({"input_query_file": input_query_file}))
    else:
        result = asyncio.run(graph.ainvoke({"input_query_file": input_query_file}))
    logger.info("✅  pipeline finished")
    return result


async def run_once_async(input_query_file: str | None = None):
    """Async variant for callers already inside an event loop."""
    logger.info("🚀  starting async Opportunity Radar run")
    if TRACING_ENABLED:
        try:
            run = client.create_run(
                project_name=project_name,
                name="opportunity_radar_pipeline_async",
                tags=["pipeline", "full_run", "async"],
                inputs={"input_query_file": input_query_file},
                run_type="chain"
            )
            if run is None:
                logger.warning("Failed to create LangSmith run, continuing without tracing")
                result = await graph.ainvoke({"input_query_file": input_query_file})
            else:
                try:
                    result = await graph.ainvoke({"input_query_file": input_query_file})
    #                client.update_run(run.id, outputs=result)
                    # ── NEW: explicit successful close ──
                    run.end(outputs={"result": result})
                    return result
                except Exception as e:
    #                client.update_run(run.id, error=str(e))
                    # ── NEW: explicit error close ──
                    run.end(error=str(e))
                    logger.error(f"Pipeline execution failed: {e}")               
                    raise
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith run: {e}")
            result = await graph.ainvoke({"input_query_file": input_query_file})
    else:
        result = await graph.ainvoke({"input_query_file": input_query_file})
    logger.info("✅  pipeline finished")
    return result


# ── 5. CLI convenience ----------------------------------------------------
if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="Run the pipeline once.")
    parser.add_argument(
        "-k", "--keywords", metavar="FILE",
        help="Path to newline‑delimited keyword list (defaults to keywords.csv)"
    )
    args = parser.parse_args()
    try:
        run_once(args.keywords)
    except KeyboardInterrupt:
        sys.exit(1)

import os, asyncio, chromadb
import openai
from openai import OpenAI, AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

# ------------------ OpenAI clients ----------------------------------------
_async_client = AsyncOpenAI()          # async – returns coroutine
_sync_client  = OpenAI()               # sync  – returns object

async def _embed_async(text: str) -> list[float]:
    """
    Pure async embedding (never blocks current thread).
    """
    logger.info("Generating embedding for text of length %d", len(text))
    resp = await _async_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        timeout=20,
    )
    logger.info("Successfully generated embedding of dimension %d", len(resp.data[0].embedding))
    return resp.data[0].embedding

def embed(text: str) -> list[float]:
    """
    Synchronous helper for scoring.py and other legacy calls.

    • If already *inside* an event-loop  → run async coroutine in it.
    • Else (normal script / REPL)        → use the real sync client.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're inside an event loop: delegate
        return loop.run_until_complete(_embed_async(text))
    except RuntimeError:
        # No running loop: safe to call the blocking client
        resp = _sync_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            timeout=20,
        )
        return resp.data[0].embedding

# Export async alias for classifier
embed_async = _embed_async



# -------- Chroma vector store --------
logger.info("Initializing ChromaDB client at data/chroma_db")
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(name="companies")
logger.info("ChromaDB collection 'companies' initialized")

async def embed_and_upsert(company_id: int, text: str):
    """Generate embedding and upsert to ChromaDB."""
    try:
        logger.info("Starting embed_and_upsert for company_id=%d", company_id)
        vec = await _embed_async(text)
        logger.info("Generated embedding for company_id=%d, dimension=%d", company_id, len(vec))
        
        # Upsert to ChromaDB
        try:
            logger.info("Attempting to upsert to ChromaDB for company_id=%d", company_id)
            collection.upsert(
                ids=[str(company_id)],
                embeddings=[vec],
                documents=[text],
                metadatas=[{"company_id": company_id}],
            )
            logger.info("Successfully upserted embedding for company_id=%d", company_id)
        except Exception as e:
            logger.error("ChromaDB upsert failed for company_id=%d: %s", company_id, str(e))
            raise
    except Exception as e:
        logger.error("Failed to embed_and_upsert for company_id=%d: %s", company_id, str(e))
        raise
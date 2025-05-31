# src/vector.py
import chromadb, os, openai, asyncio
openai.api_key = os.environ["OPENAI_API_KEY"]

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection(
    name="companies",
)

async def embed_async(text: str) -> list[float]:
    """Return embedding without blocking the event-loop."""
    resp = await openai.embeddings.acreate(          # ← async version
        model="text-embedding-3-small",
        input=text,
        request_timeout=20
    )
    return resp.data[0].embedding

def embed(text: str):
    resp = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding   # list[float]

def upsert_company(company_id: int, text: str):
    collection.upsert(
        ids=[str(company_id)],
        embeddings=[embed(text)],
        documents=[text],
        metadatas=[{"company_id": company_id}]
    )

def similarity_search(query: str, k=5):
    res = collection.query(
        query_embeddings=[embed(query)],
        n_results=k
    )
    return res
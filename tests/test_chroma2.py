import chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(path=r"C:\Users\greatakela\Documents\chroma_test\chroma_db_test")
collection = client.get_or_create_collection(name="companies")

print("Created collection.")

dummy_vec = [0.1] * 1536   # must match your embedding size!
collection.upsert(
    ids=["test1"],
    embeddings=[dummy_vec],
    documents=["This is a test doc."],
    metadatas=[{"company_id": 1}],
)

print("Successfully upserted dummy embedding!")

# Now query it back:
results = collection.query(
    query_embeddings=[dummy_vec],
    n_results=1
)
print("Query results:", results)

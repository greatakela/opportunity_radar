import chromadb
import logging
import sys
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_chroma():
    try:
        # Initialize client with explicit settings
        logger.info("Initializing ChromaDB client...")
        client = chromadb.HttpClient(
            host="localhost",
            port=8000,
            ssl=False
        )
        
        # Get or create collection
        logger.info("Getting/creating collection...")
        collection = client.get_or_create_collection(
            name="test_collection_2",
            metadata={"description": "Test collection"}
        )
        
        # Test upsert with error handling and timeout
        logger.info("Testing upsert...")
        start_time = time.time()
        try:
            collection.upsert(
                ids=["test1"],
                embeddings=[[1.0, 2.0, 3.0]],
                documents=["test document"],
                metadatas=[{"test": "metadata"}]
            )
            logger.info("Upsert successful")
        except Exception as e:
            logger.error(f"Upsert failed: {str(e)}")
            raise
        
        # Test get with error handling
        logger.info("Testing get...")
        try:
            result = collection.get(ids=["test1"])
            logger.info(f"Retrieved: {result}")
        except Exception as e:
            logger.error(f"Get failed: {str(e)}")
            raise
        
        logger.info("All tests passed!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_chroma() 
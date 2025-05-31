import chromadb
from src.db import Session, Company
import pandas as pd
import os

def query_vector_store():
    try:
        # Check if the vector store directory exists
        db_path = "data/chroma_db"
        if not os.path.exists(db_path):
            print(f"\nError: Vector store directory not found at {db_path}")
            return

        # Connect to the vector store
        print("\nConnecting to ChromaDB...")
        client = chromadb.PersistentClient(path=db_path)
        
        # List available collections
        collections = client.list_collections()
        print(f"\nAvailable collections: {[c.name for c in collections]}")
        
        if not collections:
            print("\nNo collections found in the vector store")
            return
            
        collection = client.get_collection(name="companies")
        
        # Get all items from the collection
        print("\nFetching items from collection...")
        results = collection.get()
        print("\nRaw results from collection.get():")
        print(results)
        
        # Print basic stats
        print("\nVector Store Statistics:")
        print(f"Total items: {len(results['ids'])}")
        
        # Get company details from SQLite for each ID
        print("\nFetching company details from database...")
        with Session() as ses:
            companies = []
            for company_id in results['ids']:
                try:
                    company = ses.query(Company).get(int(company_id))
                    if company:
                        companies.append({
                            'id': company.id,
                            'name': company.name,
                            'domain': company.domain,
                            'description_length': len(company.description) if company.description else 0
                        })
                except Exception as e:
                    print(f"Error processing company ID {company_id}: {str(e)}")
        
        # Convert to DataFrame for better display
        if companies:
            df = pd.DataFrame(companies)
            print("\nStored Companies:")
            print(df.to_string(index=False))
        else:
            print("\nNo companies found in the vector store")
            
    except Exception as e:
        print(f"\nError querying vector store: {str(e)}")

if __name__ == "__main__":
    query_vector_store() 
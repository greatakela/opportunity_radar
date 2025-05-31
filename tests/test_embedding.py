import openai
from src.vector import embed
import numpy as np

def test_embedding():
    # Test with a simple sentence
    text = "This is a test sentence about construction and AI technology."
    print("\nInput text:", text)
    
    # Get the embedding
    print("\nCalling OpenAI embedding...")
    embedding = embed(text)
    
    # Print details about the embedding
    print("\nEmbedding details:")
    print(f"- Type: {type(embedding)}")
    print(f"- Length: {len(embedding)} dimensions")
    print(f"- First 5 values: {embedding[:5]}")
    print(f"- Last 5 values: {embedding[-5:]}")
    print(f"- Mean value: {np.mean(embedding):.4f}")
    print(f"- Min value: {min(embedding):.4f}")
    print(f"- Max value: {max(embedding):.4f}")

if __name__ == "__main__":
    test_embedding()
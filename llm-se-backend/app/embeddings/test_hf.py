from dotenv import load_dotenv
load_dotenv()

from app.embeddings.hf_client import embed_text

if __name__ == "__main__":
    embedding = embed_text("Attention mechanism in transformers")
    print("Embedding length:", len(embedding))
    print("First 5 values:", embedding[:5])

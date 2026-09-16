from langchain_huggingface import HuggingFaceEmbeddings

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def embed_texts(texts: list[str]) -> list[list[float]]:
    return embedding_model.embed_documents(texts)

def embed_query(text: str) -> list[float]:
    return embedding_model.embed_query(text)
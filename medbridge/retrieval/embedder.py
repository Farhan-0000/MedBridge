import threading
from typing import List, Dict, Any
from fastembed import TextEmbedding, SparseTextEmbedding
from medbridge.config import get_settings

class EmbeddingClient:
    """
    Unified client for generating dense and sparse embeddings using fastembed.
    Implements a thread-safe singleton pattern with lazy loading of models.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingClient, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        settings = get_settings()
        self.dense_model_name = settings.EMBEDDING_MODEL
        self.sparse_model_name = settings.SPARSE_MODEL
        
        self._dense_model = None
        self._sparse_model = None
        self._init_lock = threading.Lock()
        self._initialized = True

    def _get_dense_model(self) -> TextEmbedding:
        if self._dense_model is None:
            with self._init_lock:
                if self._dense_model is None:
                    self._dense_model = TextEmbedding(model_name=self.dense_model_name)
        return self._dense_model

    def _get_sparse_model(self) -> SparseTextEmbedding:
        if self._sparse_model is None:
            with self._init_lock:
                if self._sparse_model is None:
                    self._sparse_model = SparseTextEmbedding(model_name=self.sparse_model_name)
        return self._sparse_model

    def embed_dense(self, text: str) -> List[float]:
        """Generate a dense embedding for a single text string."""
        model = self._get_dense_model()
        result = list(model.embed([text]))[0]
        return result.tolist()

    def embed_sparse(self, text: str) -> Dict[str, Any]:
        """Generate a sparse embedding for a single text string."""
        model = self._get_sparse_model()
        result = list(model.embed([text]))[0]
        return {
            "indices": result.indices.tolist(),
            "values": result.values.tolist()
        }

    def embed_dense_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a batch of text strings."""
        model = self._get_dense_model()
        results = model.embed(texts)
        return [res.tolist() for res in results]

    def embed_sparse_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        """Generate sparse embeddings for a batch of text strings."""
        model = self._get_sparse_model()
        results = model.embed(texts)
        return [{"indices": res.indices.tolist(), "values": res.values.tolist()} for res in results]

# Convenience accessor for dependency injection
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()

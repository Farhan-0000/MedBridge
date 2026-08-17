import asyncio
import threading
from typing import List, Tuple
from sentence_transformers import CrossEncoder
from medbridge.config import get_settings

class CrossEncoderReranker:
    """
    Service for reranking document chunks against a query using a Cross-Encoder.
    Implements thread-safe singleton initialization and offloads inference to threadpool.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CrossEncoderReranker, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        settings = get_settings()
        self.model_name = settings.RERANKER_MODEL
        self.top_k = settings.RETRIEVAL_TOP_K_RERANKED
        
        self._model = None
        self._init_lock = threading.Lock()
        self._initialized = True

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            with self._init_lock:
                if self._model is None:
                    # Model loading can take a few seconds
                    self._model = CrossEncoder(self.model_name)
        return self._model

    def _sync_rerank(self, query: str, chunks: List[str], top_k: int) -> List[Tuple[str, float]]:
        if not chunks:
            return []
            
        model = self._get_model()
        pairs = [(query, chunk) for chunk in chunks]
        
        # CrossEncoder predict returns a numpy array of scores
        scores = model.predict(pairs)
        
        # Combine chunks with scores, sort descending by score
        scored_chunks = list(zip(chunks, (float(s) for s in scores)))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k items
        return scored_chunks[:top_k]

    async def rerank(self, query: str, chunks: List[str], top_k: int = None) -> List[Tuple[str, float]]:
        """
        Asynchronously rerank chunks against a query.
        Offloads the CPU-bound inference to a separate thread to prevent blocking the event loop.
        """
        if top_k is None:
            top_k = self.top_k
            
        if not chunks:
            return []
            
        # Execute the synchronous inference in the default threadpool
        return await asyncio.to_thread(self._sync_rerank, query, chunks, top_k)

# Convenience accessor for dependency injection
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker()

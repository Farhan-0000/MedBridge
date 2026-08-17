import os
import pytest

os.environ["GROQ_API_KEY"] = "dummy"
os.environ["POSTGRES_PASSWORD"] = "password"

from medbridge.retrieval.embedder import get_embedding_client

@pytest.fixture(scope="module")
def embedder():
    # Model loading might take a few seconds on first run
    return get_embedding_client()

def test_dense_dimension_384(embedder):
    text = "Hyperkalemia management requires calcium gluconate to stabilize myocardium."
    dense = embedder.embed_dense(text)
    
    assert isinstance(dense, list)
    assert len(dense) == 384
    assert all(isinstance(x, float) for x in dense)

def test_sparse_indices_values(embedder):
    text = "Hyperkalemia management requires calcium gluconate to stabilize myocardium."
    sparse = embedder.embed_sparse(text)
    
    assert isinstance(sparse, dict)
    assert "indices" in sparse
    assert "values" in sparse
    assert isinstance(sparse["indices"], list)
    assert isinstance(sparse["values"], list)
    assert len(sparse["indices"]) == len(sparse["values"])
    assert len(sparse["indices"]) > 0

def test_batch_consistency(embedder):
    texts = [
        "Patient presents with headache.",
        "Patient presents with severe migraine and photophobia."
    ]
    
    # Dense batch check
    dense_batch = embedder.embed_dense_batch(texts)
    assert len(dense_batch) == 2
    assert len(dense_batch[0]) == 384
    assert len(dense_batch[1]) == 384
    
    # Sparse batch check
    sparse_batch = embedder.embed_sparse_batch(texts)
    assert len(sparse_batch) == 2
    assert "indices" in sparse_batch[0]
    
    # Consistency check
    dense_single = embedder.embed_dense(texts[0])
    # The arrays should be almost exactly equal, but we'll check first element
    assert abs(dense_batch[0][0] - dense_single[0]) < 1e-5

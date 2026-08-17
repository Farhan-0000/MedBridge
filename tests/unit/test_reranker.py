import os
import pytest

os.environ["GROQ_API_KEY"] = "dummy"
os.environ["POSTGRES_PASSWORD"] = "password"

from medbridge.retrieval.reranker import get_reranker

@pytest.fixture(scope="module")
def reranker():
    return get_reranker()

@pytest.mark.asyncio
async def test_empty_chunks_handling(reranker):
    result = await reranker.rerank("Query", [])
    assert result == []

@pytest.mark.asyncio
async def test_rerank_output_count(reranker):
    query = "What is the treatment for hypertension?"
    chunks = [
        "Patient ate an apple.",
        "Treatment for hypertension includes ACE inhibitors.",
        "The sky is blue today.",
        "Amlodipine is a calcium channel blocker used for high blood pressure.",
        "Blood pressure reading was 120/80.",
        "Lisinopril is often prescribed."
    ]
    result = await reranker.rerank(query, chunks, top_k=3)
    
    assert len(result) == 3
    # Check return types
    assert isinstance(result[0], tuple)
    assert isinstance(result[0][0], str)
    assert isinstance(result[0][1], float)

@pytest.mark.asyncio
async def test_score_sorting_descending(reranker):
    query = "hypertension medication"
    chunks = [
        "I like cats and dogs.",
        "Amlodipine 5mg daily for hypertension.",
        "Random irrelevant text about weather."
    ]
    result = await reranker.rerank(query, chunks, top_k=3)
    
    assert len(result) == 3
    # Check it is sorted descending by score
    assert result[0][1] >= result[1][1] >= result[2][1]
    
    # The most relevant should be the medication one
    assert "Amlodipine" in result[0][0]

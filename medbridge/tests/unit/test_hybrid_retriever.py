"""
Unit tests for Qdrant Hybrid Retriever (retrieval/hybrid_retriever.py).
Tests mock Qdrant client responses, error handling, and score mapping.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from qdrant_client import models
from qdrant_client.http import models as http_models
from qdrant_client.http.exceptions import UnexpectedResponse

from medbridge.retrieval.hybrid_retriever import (
    HybridRetriever,
    RetrievedChunk,
    get_hybrid_retriever,
)


@pytest.fixture
def mock_embedder():
    embedder = MagicMock()
    # Mock dense embedding (384 floats)
    embedder.embed_dense.return_value = [0.1] * 384
    # Mock sparse embedding
    embedder.embed_sparse.return_value = {
        "indices": [10, 42, 99],
        "values": [0.5, 0.8, 1.2],
    }
    return embedder


@pytest.fixture
def mock_qdrant_client():
    client = AsyncMock()
    return client


@pytest.fixture
def retriever(mock_qdrant_client, mock_embedder):
    return HybridRetriever(
        client=mock_qdrant_client,
        embedder=mock_embedder,
        collection_name="clinical_guidelines",
    )


@pytest.mark.asyncio
async def test_empty_or_whitespace_query_returns_empty_list(retriever):
    assert await retriever.hybrid_search("") == []
    assert await retriever.hybrid_search("   ") == []
    assert await retriever.retrieve("") == []
    assert await retriever.retrieve("   ") == []


@pytest.mark.asyncio
async def test_hybrid_search_query_construction_and_prefetch(retriever, mock_qdrant_client, mock_embedder):
    # Setup mock return points
    mock_point = models.ScoredPoint(
        id="pt_1",
        version=1,
        score=0.0333,
        payload={
            "chunk_id": "aha_2025_s1_c1",
            "chunk_text": "Hypertension first line treatment includes ACE inhibitors.",
            "guideline_id": "AHA_ACC_2025",
            "section_title": "Pharmacologic Treatment",
            "page_number": 15,
            "source_url": "https://guidelines.ahajournals.org/htn2025",
        },
    )
    mock_qdrant_client.query_points.return_value = http_models.QueryResponse(points=[mock_point])

    results = await retriever.hybrid_search("hypertension treatment", top_k=10)

    # 1. Verify embedder calls
    mock_embedder.embed_dense.assert_called_once_with("hypertension treatment")
    mock_embedder.embed_sparse.assert_called_once_with("hypertension treatment")

    # 2. Verify Qdrant query_points call
    mock_qdrant_client.query_points.assert_awaited_once()
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert call_kwargs["collection_name"] == "clinical_guidelines"
    assert call_kwargs["limit"] == 10

    # Prefetch inspection
    prefetch = call_kwargs["prefetch"]
    assert len(prefetch) == 2
    assert prefetch[0].using == "dense"
    assert prefetch[0].query == [0.1] * 384
    assert prefetch[0].limit == 10

    assert prefetch[1].using == "sparse"
    assert prefetch[1].query.indices == [10, 42, 99]
    assert prefetch[1].query.values == [0.5, 0.8, 1.2]
    assert prefetch[1].limit == 10

    # Fusion query inspection
    assert isinstance(call_kwargs["query"], models.FusionQuery)
    assert call_kwargs["query"].fusion == models.Fusion.RRF

    # 3. Verify returned chunk mapping
    assert len(results) == 1
    chunk = results[0]
    assert isinstance(chunk, RetrievedChunk)
    assert chunk.chunk_id == "aha_2025_s1_c1"
    assert chunk.chunk_text == "Hypertension first line treatment includes ACE inhibitors."
    assert chunk.guideline_id == "AHA_ACC_2025"
    assert chunk.section_title == "Pharmacologic Treatment"
    assert chunk.page_number == 15
    assert chunk.source_url == "https://guidelines.ahajournals.org/htn2025"
    assert abs(chunk.score - 0.0333) < 1e-4


@pytest.mark.asyncio
async def test_score_and_missing_payload_fallback(retriever, mock_qdrant_client):
    # Point with missing payload fields
    pt_sparse_payload = http_models.ScoredPoint(
        id="pt_uuid_999",
        version=1,
        score=0.0166,
        payload=None,
    )
    # Mock point with None score to verify score fallback
    pt_none_score = MagicMock()
    pt_none_score.id = "pt_uuid_888"
    pt_none_score.score = None
    pt_none_score.payload = {"chunk_id": "chunk_custom"}

    mock_qdrant_client.query_points.return_value = MagicMock(
        points=[pt_sparse_payload, pt_none_score]
    )

    results = await retriever.hybrid_search("heart failure")

    assert len(results) == 2

    # Point 1 fallbacks
    assert results[0].chunk_id == "pt_uuid_999"
    assert results[0].chunk_text == ""
    assert results[0].guideline_id == ""
    assert results[0].section_title == ""
    assert results[0].page_number == 0
    assert results[0].source_url == ""
    assert abs(results[0].score - 0.0166) < 1e-4

    # Point 2 fallbacks
    assert results[1].chunk_id == "chunk_custom"
    assert results[1].score == 0.0


@pytest.mark.asyncio
async def test_retrieve_alias_calls_hybrid_search(retriever, mock_qdrant_client):
    mock_point = http_models.ScoredPoint(
        id="pt_1",
        version=1,
        score=0.5,
        payload={"chunk_id": "c1", "chunk_text": "Sample text"},
    )
    mock_qdrant_client.query_points.return_value = http_models.QueryResponse(points=[mock_point])

    results = await retriever.retrieve("cardiac arrest", top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == "c1"



@pytest.mark.asyncio
async def test_graceful_handling_on_qdrant_connection_error(retriever, mock_qdrant_client):
    mock_qdrant_client.query_points.side_effect = ConnectionError("Qdrant connection refused")

    results = await retriever.hybrid_search("query during network outage")
    assert results == []


@pytest.mark.asyncio
async def test_graceful_handling_on_unexpected_response(retriever, mock_qdrant_client):
    mock_qdrant_client.query_points.side_effect = UnexpectedResponse(
        status_code=404,
        reason_phrase="Not Found",
        content=b'{"status":{"error":"Collection not found"}}',
        headers={},
    )

    results = await retriever.hybrid_search("query on missing collection")
    assert results == []


@pytest.mark.asyncio
async def test_graceful_handling_on_embedder_failure(retriever, mock_embedder):
    mock_embedder.embed_dense.side_effect = RuntimeError("Embedding model runtime failure")

    results = await retriever.hybrid_search("query when model crashes")
    assert results == []


@pytest.mark.asyncio
async def test_close_client_connection(retriever, mock_qdrant_client):
    await retriever.close()
    mock_qdrant_client.close.assert_awaited_once()


def test_factory_function():
    retriever_inst = get_hybrid_retriever()
    assert isinstance(retriever_inst, HybridRetriever)

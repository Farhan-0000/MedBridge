"""
Integration Verification for Production Guideline Collection Indexing (TASK-34).

Verifies:
1. Production Qdrant collection 'clinical_guidelines' is created with 384-dim dense
   and BM25 sparse vector configurations.
2. All guideline PDFs (AHA/ACC 2025, ESC/ESH 2024, MedlinePlus) are fully indexed
   without chunk validation errors (points count >= 15).
3. Hybrid retrieval returns non-empty top-K search results across key clinical topics.
4. Payloads contain all required schema fields (chunk_id, guideline_id, section_title, page_number, chunk_text).
"""
import pytest
from qdrant_client import AsyncQdrantClient, models

from medbridge.config import get_settings
from medbridge.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk


COLLECTION_NAME = "clinical_guidelines"


@pytest.fixture
async def live_qdrant_client():
    """Connect to live Qdrant instance."""
    settings = get_settings()
    client = AsyncQdrantClient(url=settings.QDRANT_URL)
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_collection_configuration(live_qdrant_client: AsyncQdrantClient):
    """Verify collection exists with 384-dim dense and BM25 sparse configurations."""
    collections = await live_qdrant_client.get_collections()
    collection_names = [c.name for c in collections.collections]
    assert COLLECTION_NAME in collection_names, f"Collection '{COLLECTION_NAME}' not found in Qdrant!"

    info = await live_qdrant_client.get_collection(collection_name=COLLECTION_NAME)
    
    # 1. Verify dense vector configuration
    vectors_config = info.config.params.vectors
    assert "dense" in vectors_config
    assert vectors_config["dense"].size == 384
    assert vectors_config["dense"].distance == models.Distance.COSINE

    # 2. Verify sparse vector configuration
    sparse_config = info.config.params.sparse_vectors
    assert sparse_config is not None
    assert "sparse" in sparse_config
    assert sparse_config["sparse"].modifier == models.Modifier.IDF


@pytest.mark.asyncio
async def test_collection_point_count_and_guideline_representation(live_qdrant_client: AsyncQdrantClient):
    """Verify all guideline documents are indexed with point count >= 15."""
    info = await live_qdrant_client.get_collection(collection_name=COLLECTION_NAME)
    assert info.points_count >= 15, f"Expected at least 15 points, found {info.points_count}"

    # Scroll points to check guideline representation
    scroll_result = await live_qdrant_client.scroll(
        collection_name=COLLECTION_NAME,
        limit=50,
        with_payload=True,
        with_vectors=False,
    )
    points = scroll_result[0]
    assert len(points) >= 15

    represented_guidelines = {p.payload.get("guideline_id") for p in points}
    assert "AHA_ACC_2025" in represented_guidelines
    assert "ESC_ESH_2024" in represented_guidelines
    assert "MEDLINEPLUS" in represented_guidelines

    # Validate payload integrity
    for p in points:
        payload = p.payload
        assert payload.get("chunk_id")
        assert payload.get("guideline_id")
        assert payload.get("section_title")
        assert isinstance(payload.get("page_number"), int) and payload.get("page_number") >= 1
        assert len(payload.get("chunk_text", "").strip()) >= 10


@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected_keyword", [
    ("hypertension diagnostic criteria and blood pressure thresholds", "blood pressure"),
    ("first line pharmacotherapy calcium channel blocker amlodipine", "therapy"),
    ("lifestyle modifications sodium restriction DASH diet", "diet"),
    ("resistant hypertension aldosterone antagonist spironolactone", "hypertension"),
])
async def test_hybrid_search_across_clinical_topics(
    live_qdrant_client: AsyncQdrantClient,
    query: str,
    expected_keyword: str,
):
    """Verify hybrid search returns non-empty top-K results across key clinical topics."""
    retriever = HybridRetriever(client=live_qdrant_client, collection_name=COLLECTION_NAME)

    chunks = await retriever.hybrid_search(query=query, top_k=3)
    assert len(chunks) > 0, f"No chunks returned for clinical query: '{query}'"
    
    for c in chunks:
        assert isinstance(c, RetrievedChunk)
        assert c.chunk_id
        assert c.guideline_id in {"AHA_ACC_2025", "ESC_ESH_2024", "MEDLINEPLUS"}
        assert len(c.chunk_text) > 20
        assert c.score > 0.0

    combined_text = " ".join(c.chunk_text.lower() for c in chunks)
    assert expected_keyword in combined_text, f"Expected '{expected_keyword}' in search results for query '{query}'"

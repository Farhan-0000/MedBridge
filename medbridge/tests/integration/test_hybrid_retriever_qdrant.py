"""
Integration tests for Qdrant Hybrid Retriever (retrieval/hybrid_retriever.py).
Verifies real dense + sparse embedding generation and Qdrant RRF hybrid search
against an in-memory test collection.
"""
import pytest
from qdrant_client import AsyncQdrantClient, models

from medbridge.retrieval.embedder import get_embedding_client
from medbridge.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk

COLLECTION_NAME = "test_clinical_guidelines"
EMPTY_COLLECTION_NAME = "test_empty_guidelines"


@pytest.fixture(scope="module")
def real_embedder():
    """Real FastEmbed dense and sparse embedding client."""
    return get_embedding_client()


@pytest.fixture(scope="module")
async def populated_qdrant_client(real_embedder):
    """
    In-memory AsyncQdrantClient populated with real dense and sparse vectors
    for clinical guideline chunks.
    """
    client = AsyncQdrantClient(location=":memory:")

    # 1. Create collection with dense (384-dim, Cosine) and sparse (IDF)
    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )

    # 2. Create empty collection for edge case testing
    await client.create_collection(
        collection_name=EMPTY_COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )

    # 3. Sample clinical guideline chunks
    documents = [
        {
            "id": 1,
            "chunk_id": "aha_acc_2025_htn_c1",
            "chunk_text": "First-line pharmacologic therapy for primary hypertension in non-black patients includes thiazide diuretics, CCBs, and ACE inhibitors or ARBs.",
            "guideline_id": "AHA_ACC_2025",
            "section_title": "First-Line Pharmacologic Therapy",
            "page_number": 24,
            "source_url": "https://guidelines.acc.org/htn2025",
        },
        {
            "id": 2,
            "chunk_id": "ada_2024_dm2_c1",
            "chunk_text": "First-line therapy for type 2 diabetes consists of metformin and comprehensive lifestyle modification.",
            "guideline_id": "ADA_2024",
            "section_title": "Pharmacologic Approaches to Glycemic Treatment",
            "page_number": 105,
            "source_url": "https://diabetesjournals.org/care/2024",
        },
        {
            "id": 3,
            "chunk_id": "acc_aha_2023_hf_c1",
            "chunk_text": "Guideline-directed medical therapy (GDMT) for heart failure with reduced ejection fraction (HFrEF) includes ARNi/ACEi/ARB, beta-blocker, MRA, and SGLT2 inhibitor.",
            "guideline_id": "ACC_AHA_2023",
            "section_title": "Guideline-Directed Medical Therapy for HFrEF",
            "page_number": 42,
            "source_url": "https://guidelines.acc.org/hf2023",
        },
    ]

    points = []
    for doc in documents:
        text = doc["chunk_text"]
        dense_vec = real_embedder.embed_dense(text)
        sparse_dict = real_embedder.embed_sparse(text)
        sparse_vec = models.SparseVector(
            indices=sparse_dict["indices"],
            values=sparse_dict["values"],
        )

        point = models.PointStruct(
            id=doc["id"],
            vector={
                "dense": dense_vec,
                "sparse": sparse_vec,
            },
            payload={
                "chunk_id": doc["chunk_id"],
                "chunk_text": doc["chunk_text"],
                "guideline_id": doc["guideline_id"],
                "section_title": doc["section_title"],
                "page_number": doc["page_number"],
                "source_url": doc["source_url"],
            },
        )
        points.append(point)

    await client.upsert(collection_name=COLLECTION_NAME, points=points)

    yield client

    await client.close()


@pytest.fixture
def real_retriever(populated_qdrant_client, real_embedder):
    return HybridRetriever(
        client=populated_qdrant_client,
        embedder=real_embedder,
        collection_name=COLLECTION_NAME,
    )


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_hypertension_query(real_retriever):
    query = "What is the first-line medication for primary hypertension?"
    chunks = await real_retriever.hybrid_search(query, top_k=2)

    assert len(chunks) > 0
    top_chunk = chunks[0]
    assert isinstance(top_chunk, RetrievedChunk)
    assert top_chunk.chunk_id == "aha_acc_2025_htn_c1"
    assert top_chunk.guideline_id == "AHA_ACC_2025"
    assert "thiazide" in top_chunk.chunk_text.lower()
    assert top_chunk.page_number == 24
    assert top_chunk.source_url == "https://guidelines.acc.org/htn2025"
    assert top_chunk.score > 0.0


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_diabetes_query(real_retriever):
    query = "Metformin initial therapy for type 2 diabetes glycemic control"
    chunks = await real_retriever.hybrid_search(query, top_k=2)

    assert len(chunks) > 0
    top_chunk = chunks[0]
    assert top_chunk.chunk_id == "ada_2024_dm2_c1"
    assert top_chunk.guideline_id == "ADA_2024"
    assert "metformin" in top_chunk.chunk_text.lower()


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_heart_failure_query(real_retriever):
    query = "GDMT for heart failure with reduced ejection fraction SGLT2 beta-blocker"
    chunks = await real_retriever.retrieve(query, top_k=2)

    assert len(chunks) > 0
    top_chunk = chunks[0]
    assert top_chunk.chunk_id == "acc_aha_2023_hf_c1"
    assert top_chunk.guideline_id == "ACC_AHA_2023"
    assert "hfref" in top_chunk.chunk_text.lower()


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_empty_query(real_retriever):
    chunks = await real_retriever.hybrid_search("")
    assert chunks == []

    chunks_whitespace = await real_retriever.hybrid_search("   \n\t  ")
    assert chunks_whitespace == []


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_empty_collection(populated_qdrant_client, real_embedder):
    empty_retriever = HybridRetriever(
        client=populated_qdrant_client,
        embedder=real_embedder,
        collection_name=EMPTY_COLLECTION_NAME,
    )
    chunks = await empty_retriever.hybrid_search("hypertension medication")
    assert chunks == []


@pytest.mark.asyncio
async def test_real_hybrid_retrieval_nonexistent_collection(populated_qdrant_client, real_embedder):
    missing_retriever = HybridRetriever(
        client=populated_qdrant_client,
        embedder=real_embedder,
        collection_name="nonexistent_collection_xyz_404",
    )
    chunks = await missing_retriever.hybrid_search("hypertension medication")
    # Must handle gracefully and return empty list
    assert chunks == []

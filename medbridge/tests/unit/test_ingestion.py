"""
Unit tests for TASK-24: Knowledge Ingestion CLI Pipeline (Module M-18).

Tests:
1. PDF parser page and text extraction using PyMuPDF.
2. Section-aware chunking, token limits, and overlap windows.
3. Payload schema validation.
4. Qdrant indexer and --dry-run write bypass.
5. CLI argument parsing.
"""
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import pymupdf

from medbridge.ingestion.__main__ import build_arg_parser, run_ingestion
from medbridge.ingestion.chunker import (
    RawChunk,
    SectionAwareChunker,
    count_tokens,
)
from medbridge.ingestion.indexer import (
    ChunkValidationError,
    QdrantIndexer,
    validate_chunk_payload,
)
from medbridge.ingestion.parser import (
    PDFParseError,
    ParsedDocument,
    ParsedPage,
    deduce_guideline_id,
    extract_pages_from_pdf,
)


# ---------------------------------------------------------------------------
# 1. PDF Parser Tests
# ---------------------------------------------------------------------------

class TestPDFParser:
    """Verify PyMuPDF text and page extraction from guideline PDFs."""

    def test_deduce_guideline_id(self) -> None:
        assert deduce_guideline_id("aha_acc_2025_hypertension.pdf") == "AHA_ACC_2025"
        assert deduce_guideline_id("ESC_ESH_2024.pdf") == "ESC_ESH_2024"
        assert deduce_guideline_id("medlineplus_blood_pressure.pdf") == "MEDLINEPLUS"
        assert deduce_guideline_id("custom_guideline_v2.pdf") == "CUSTOM_GUIDELINE_V2"

    def test_extract_pages_from_real_pdf(self, tmp_path: Path) -> None:
        """Create a real PDF in memory and verify extraction."""
        pdf_file = tmp_path / "aha_acc_2025_test.pdf"

        # Create a small 2-page PDF using PyMuPDF
        doc = pymupdf.open()
        p1 = doc.new_page()
        p1.insert_text((50, 50), "Section 1: Diagnostic Criteria for Hypertension\nBlood pressure >= 130/80.")
        p2 = doc.new_page()
        p2.insert_text((50, 50), "Section 2: Pharmacologic Treatment\nFirst-line therapy includes CCBs.")
        doc.save(str(pdf_file))
        doc.close()

        parsed = extract_pages_from_pdf(pdf_file)

        assert isinstance(parsed, ParsedDocument)
        assert parsed.guideline_id == "AHA_ACC_2025"
        assert parsed.total_pages == 2
        assert parsed.pages[0].page_number == 1
        assert "Diagnostic Criteria" in parsed.pages[0].text
        assert parsed.pages[1].page_number == 2
        assert "Pharmacologic Treatment" in parsed.pages[1].text

    def test_nonexistent_pdf_raises_error(self, tmp_path: Path) -> None:
        missing_file = tmp_path / "does_not_exist.pdf"
        with pytest.raises(PDFParseError) as exc_info:
            extract_pages_from_pdf(missing_file)
        assert "File does not exist" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Section-Aware Chunker Tests (Token Limits & Overlap)
# ---------------------------------------------------------------------------

class TestSectionAwareChunker:
    """Verify section-aware splitting, token limit enforcement, and overlap."""

    def test_section_header_detection(self) -> None:
        chunker = SectionAwareChunker(chunk_size=100, chunk_overlap=20)
        assert chunker.is_section_header("Section 8: Pharmacological Treatment") is True
        assert chunker.is_section_header("Chapter 3: Diagnostics") is True
        assert chunker.is_section_header("8.2 First-Line Therapy") is True
        assert chunker.is_section_header("RECOMMENDATIONS FOR PATIENTS") is True
        assert chunker.is_section_header("This is ordinary body paragraph text.") is False

    def test_chunking_token_limits_and_overlap(self) -> None:
        """Verify that chunks adhere to chunk_size and share chunk_overlap tokens."""
        chunk_size = 50
        chunk_overlap = 10
        chunker = SectionAwareChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        # Generate a text of 120 words
        words = [f"word{i}" for i in range(1, 121)]
        text = " ".join(words)

        chunks = chunker.chunk_text(
            text=text,
            guideline_id="AHA_2025",
            page_number=1,
            initial_section="General",
        )

        assert len(chunks) > 1

        for c in chunks:
            # Token count must be within limit
            token_count = count_tokens(c.chunk_text)
            assert token_count <= chunk_size

        # Check overlap between chunk 0 and chunk 1
        # Chunk 0 words: words 0..50
        # Chunk 1 words: words (50 - 10)..min(50-10+50, 120) = words 40..90
        # Overlapping words should be words 40..49
        chunk0_text = chunks[0].chunk_text
        chunk1_text = chunks[1].chunk_text
        for i in range(41, 50):
            assert f"word{i}" in chunk0_text
            assert f"word{i}" in chunk1_text

    def test_section_headers_preserved_in_chunks(self) -> None:
        chunker = SectionAwareChunker(chunk_size=100, chunk_overlap=10)
        content = (
            "Section 1: Initial Diagnosis\n"
            "Patients with elevated blood pressure should be evaluated with ambulatory monitoring.\n\n"
            "Section 2: Lifestyle Modifications\n"
            "Sodium restriction and regular physical exercise are recommended for all patients."
        )

        doc = ParsedDocument(
            guideline_id="AHA_2025",
            file_path="test.pdf",
            pages=[ParsedPage(page_number=1, text=content)],
        )
        chunks = chunker.chunk_document(doc)

        assert len(chunks) == 2
        assert chunks[0].section_title == "Section 1: Initial Diagnosis"
        assert "Section 1: Initial Diagnosis" in chunks[0].chunk_text
        assert "ambulatory monitoring" in chunks[0].chunk_text

        assert chunks[1].section_title == "Section 2: Lifestyle Modifications"
        assert "Section 2: Lifestyle Modifications" in chunks[1].chunk_text
        assert "Sodium restriction" in chunks[1].chunk_text

    def test_invalid_chunk_parameters_raise_value_error(self) -> None:
        with pytest.raises(ValueError):
            SectionAwareChunker(chunk_size=0)

        with pytest.raises(ValueError):
            SectionAwareChunker(chunk_size=50, chunk_overlap=50)


# ---------------------------------------------------------------------------
# 3. Payload Schema Validation Tests
# ---------------------------------------------------------------------------

class TestPayloadSchemaValidation:
    """Verify schema constraints for Qdrant payload integrity."""

    def test_valid_payload_accepted(self) -> None:
        valid_chunk = RawChunk(
            chunk_id="aha_2025_s1_c1",
            guideline_id="AHA_ACC_2025",
            section_title="Diagnosis",
            page_number=3,
            chunk_text="Hypertension is defined as systolic >= 130 mm Hg.",
            source_url="https://guidelines.acc.org/htn2025",
        )
        assert validate_chunk_payload(valid_chunk) is True

    def test_missing_or_empty_chunk_id_rejected(self) -> None:
        with pytest.raises(ChunkValidationError):
            validate_chunk_payload(
                RawChunk(
                    chunk_id="   ",
                    guideline_id="AHA",
                    section_title="Sec",
                    page_number=1,
                    chunk_text="Valid chunk text exceeding five chars",
                )
            )

    def test_invalid_page_number_rejected(self) -> None:
        with pytest.raises(ChunkValidationError):
            validate_chunk_payload(
                RawChunk(
                    chunk_id="c1",
                    guideline_id="AHA",
                    section_title="Sec",
                    page_number=0,  # 1-indexed required
                    chunk_text="Valid chunk text",
                )
            )

    def test_empty_or_too_short_text_rejected(self) -> None:
        with pytest.raises(ChunkValidationError):
            validate_chunk_payload(
                RawChunk(
                    chunk_id="c1",
                    guideline_id="AHA",
                    section_title="Sec",
                    page_number=1,
                    chunk_text="Hi",  # < 5 chars
                )
            )


# ---------------------------------------------------------------------------
# 4. Qdrant Indexer & Dry-Run Tests
# ---------------------------------------------------------------------------

class TestQdrantIndexer:
    """Verify vector computation, collection configuration, and dry-run write bypass."""

    @pytest.fixture
    def mock_embedder(self):
        embedder = MagicMock()
        embedder.embed_dense.return_value = [0.1] * 384
        embedder.embed_sparse.return_value = {"indices": [1, 2], "values": [0.5, 0.9]}
        return embedder

    @pytest.fixture
    def mock_qdrant_client(self):
        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        return client

    def test_dry_run_bypasses_qdrant_writes(self, mock_qdrant_client, mock_embedder) -> None:
        """--dry-run validates chunks and skips Qdrant upsert and collection creation."""
        indexer = QdrantIndexer(client=mock_qdrant_client, embedder=mock_embedder)
        chunks = [
            RawChunk(
                chunk_id="c1",
                guideline_id="AHA_2025",
                section_title="Sec1",
                page_number=1,
                chunk_text="Sample valid chunk content text.",
            )
        ]

        count = indexer.index_chunks(
            chunks=chunks,
            collection_name="clinical_guidelines",
            dry_run=True,
        )

        assert count == 1
        # Qdrant client must NOT have been called
        mock_qdrant_client.create_collection.assert_not_called()
        mock_qdrant_client.upsert.assert_not_called()

    def test_live_indexing_creates_collection_and_upserts(self, mock_qdrant_client, mock_embedder) -> None:
        """Live run provisions collection and upserts PointStruct batch."""
        indexer = QdrantIndexer(client=mock_qdrant_client, embedder=mock_embedder)
        chunks = [
            RawChunk(
                chunk_id="c1",
                guideline_id="AHA_2025",
                section_title="Sec1",
                page_number=1,
                chunk_text="First chunk text content.",
            ),
            RawChunk(
                chunk_id="c2",
                guideline_id="AHA_2025",
                section_title="Sec2",
                page_number=2,
                chunk_text="Second chunk text content.",
            ),
        ]

        count = indexer.index_chunks(
            chunks=chunks,
            collection_name="clinical_guidelines",
            recreate=True,
            dry_run=False,
        )

        assert count == 2
        mock_qdrant_client.create_collection.assert_called_once()
        mock_qdrant_client.upsert.assert_called_once()

        # Check upsert call arguments
        upsert_kwargs = mock_qdrant_client.upsert.call_args.kwargs
        assert upsert_kwargs["collection_name"] == "clinical_guidelines"
        assert len(upsert_kwargs["points"]) == 2


# ---------------------------------------------------------------------------
# 5. CLI Parser & Execution Tests
# ---------------------------------------------------------------------------

class TestCLI:
    """Verify argument parsing and CLI coordination."""

    def test_build_arg_parser(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([
            "--pdf-dir", "./data/guidelines",
            "--qdrant-url", "http://127.0.0.1:6333",
            "--collection", "clinical_guidelines",
            "--chunk-size", "512",
            "--chunk-overlap", "64",
            "--recreate",
            "--dry-run",
        ])

        assert args.pdf_dir == "./data/guidelines"
        assert args.qdrant_url == "http://127.0.0.1:6333"
        assert args.collection == "clinical_guidelines"
        assert args.chunk_size == 512
        assert args.chunk_overlap == 64
        assert args.recreate is True
        assert args.dry_run is True

    def test_run_ingestion_empty_dir(self, tmp_path: Path) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["--pdf-dir", str(tmp_path), "--dry-run"])
        exit_code = run_ingestion(args)
        assert exit_code == 0

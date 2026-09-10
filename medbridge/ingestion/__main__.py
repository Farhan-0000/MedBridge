"""
Knowledge Ingestion Pipeline CLI Entry Point (Module M-18, Ingestion Pipeline).

Parses clinical guideline PDFs, segments text into section-aware chunks,
computes dense and sparse BM25 vectors, and indexes them into Qdrant.

Usage:
    python -m medbridge.ingestion --pdf-dir ./data/guidelines/ --dry-run
    python -m medbridge.ingestion --pdf-dir ./data/guidelines/ --recreate

Technical Specification Part V §3.4, §4.3.
"""
import argparse
import logging
import sys
from pathlib import Path

from medbridge.ingestion.chunker import SectionAwareChunker
from medbridge.ingestion.indexer import QdrantIndexer
from medbridge.ingestion.parser import PDFParseError, extract_pages_from_pdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("medbridge.ingestion")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ingestion CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m medbridge.ingestion",
        description="MedBridge Offline Clinical Guideline PDF Ingestion & Indexing Pipeline.",
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        required=True,
        help="Path to directory containing guideline PDFs",
    )
    parser.add_argument(
        "--qdrant-url",
        type=str,
        default="http://127.0.0.1:6333",
        help="Qdrant server URL (default: http://127.0.0.1:6333)",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="clinical_guidelines",
        help="Target collection name (default: clinical_guidelines)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Token count per chunk (default: 512)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=64,
        help="Overlap tokens between adjacent chunks (default: 64)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        default=False,
        help="Drop and recreate collection before indexing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Parse and validate only, do not write to Qdrant",
    )
    return parser


def run_ingestion(args: argparse.Namespace) -> int:
    """Execute the complete ingestion workflow given parsed CLI arguments.

    Returns:
        0 on success, 1 on critical error.
    """
    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        logger.error("PDF directory does not exist or is not a directory: %s", pdf_dir)
        return 1

    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in directory: %s", pdf_dir)
        return 0

    logger.info("Found %d PDF document(s) in %s", len(pdf_files), pdf_dir)

    # 1. Parse all PDF documents
    parsed_docs = []
    for pdf_path in pdf_files:
        try:
            doc = extract_pages_from_pdf(pdf_path)
            parsed_docs.append(doc)
        except PDFParseError as e:
            logger.error("Failed to parse PDF '%s', skipping: %s", pdf_path.name, e)

    if not parsed_docs:
        logger.error("No documents could be parsed successfully")
        return 1

    # 2. Section-aware chunking
    chunker = SectionAwareChunker(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    all_chunks = []
    for doc in parsed_docs:
        doc_chunks = chunker.chunk_document(doc)
        all_chunks.extend(doc_chunks)

    logger.info("Total chunks generated across all documents: %d", len(all_chunks))

    # 3. Vectorization and Indexing
    indexer = QdrantIndexer(qdrant_url=args.qdrant_url)
    total_processed = indexer.index_chunks(
        chunks=all_chunks,
        collection_name=args.collection,
        recreate=args.recreate,
        dry_run=args.dry_run,
    )

    mode_label = "VALIDATED (DRY-RUN)" if args.dry_run else "INDEXED"
    logger.info(
        "Ingestion completed: %d documents parsed, %d chunks %s into collection '%s'",
        len(parsed_docs),
        total_processed,
        mode_label,
        args.collection,
    )
    return 0


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    exit_code = run_ingestion(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

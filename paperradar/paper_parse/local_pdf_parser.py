#!/usr/bin/env python3
# Local MinerU parsing helper for PaperRadar.

"""
Streamlined local PDF parsing pipeline for MinerU.

This script provides a simple command-line interface for processing local PDF files
through the MinerU service with automatic upload, polling, download, and LLM enhancement.

Usage:
    # Process all PDFs in data/
    python local_pdf_parser.py --all

    # Process specific PDFs
    python local_pdf_parser.py file1.pdf file2.pdf

    # With custom options
    python local_pdf_parser.py --all --max-retries 5 --no-llm-aid --output-dir ./my_output
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from loguru import logger
# Import PaperProcessor
from .paper_processor import PaperProcessor
from .utils import validate_pdf_files

# Configure logging
log_dir = "./logs/local_pdf_parser"
os.makedirs(log_dir, exist_ok=True)
logger.add(
    sink=os.path.join(log_dir, "pipeline_{time}.log"),
    rotation="100 MB",
    retention="7 days",
    encoding="utf-8",
)

_MODULE_ROOT = Path(__file__).resolve().parent
# Prefer project/.env, then module-local fallback.
load_dotenv(dotenv_path=_MODULE_ROOT.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT.parent.parent / ".env")
load_dotenv(dotenv_path=_MODULE_ROOT / ".env")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Streamlined local PDF parsing pipeline for MinerU",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
# Process all PDFs in data/
python local_pdf_parser.py --all

# Process specific PDFs
python local_pdf_parser.py paper1.pdf paper2.pdf

# Process with custom output directory
python local_pdf_parser.py --all --output-dir ./my_output

# Disable LLM enhancement
python local_pdf_parser.py --all --no-llm-aid

# Increase retry attempts
python local_pdf_parser.py --all --max-retries 5
""",
    )

    # Input options
    parser.add_argument("--all", action="store_true", help="Process all PDF files in data/ directory")
    parser.add_argument("pdf_files", nargs="*", help="Specific PDF filenames to process (relative to data/)")

    # Processing options
    parser.add_argument("--data-dir", type=str, default="data", help="Directory containing PDF files (default: data/)")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory for output results (default: output/)")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum retry attempts for failed operations (default: 3)")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=True,
        help="Continue processing remaining files on error (default: True)",
    )
    parser.add_argument("--fail-on-error", action="store_false", dest="continue_on_error", help="Stop processing immediately on any error")

    # MinerU options
    parser.add_argument(
        "--model-version", type=str, default="vlm", choices=["vlm", "pipeline"], help="MinerU model version (default: vlm)"
    )
    parser.add_argument("--language", type=str, default="en", help="Language for OCR (default: en)")
    parser.add_argument("--no-ocr", action="store_false", dest="is_ocr", help="Disable OCR processing")
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait for MinerU processing (default: 300)",
    )

    # LLM options
    parser.add_argument("--llm-aid", action=argparse.BooleanOptionalAction, default=True, help="Enable LLM-aided title optimization (default: True)")

    # Logging options
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--save-summary", action="store_true", help="Save processing summary to JSON")

    return parser.parse_args()

def parse_local_pdfs(
    process_all=False,                  # process all PDF files in data_dir
    specific_pdf_files=None,            # specific PDF files to process
    data_dir="./data",                  # data directory
    output_dir="./output",              # output directory
    max_retries=3,                      # maximum retry attempts for failed operations
    continue_on_error=True,             # continue processing remaining files on error
    file_on_error=None,                 # file to save error messages
    model_version="vlm",                # model version
    language="en",                      # language for OCR
    is_ocr=False,                       # disable OCR
    poll_timeout=300,                   # maximum seconds to wait for MinerU processing
    llm_aid=True,                       # enable LLM-aided title optimization
    verbose=False,                      # enable verbose logging
    save_summary=False,                 # save processing summary to JSON
):
    """
    Parse the PDF files.
    """
    # Configure verbose logging if requested
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # Log configuration
    logger.info("=" * 80)
    logger.info("Local PDF Parsing Pipeline - Starting")
    logger.info("=" * 80)

    # Validate input: either --all or pdf_files must be specified, but not both
    if process_all and specific_pdf_files:
        logger.error("Cannot specify both --all and specific PDF files")
        logger.error("Use either: --all OR file1.pdf file2.pdf ...")
        return

    if not process_all and not specific_pdf_files:
        logger.error("Must specify either process_all or at least one PDF file")
        logger.error("Examples:")
        logger.error("  python local_pdf_parser.py --all")
        logger.error("  python local_pdf_parser.py paper1.pdf paper2.pdf")
        return

    # Validate data directory exists
    if not os.path.isdir(data_dir):
        logger.error(f"Data directory does not exist: {data_dir}")
        logger.error("Please create it and add PDF files before running.")
        return

    # Determine which PDFs to process
    if process_all:
        pdf_files = [f for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
        if not pdf_files:
            logger.error(f"No PDF files found in {data_dir}")
            return
        logger.info(f"Found {len(pdf_files)} PDF files in {data_dir}")
    else:
        try:
            pdf_files = validate_pdf_files(specific_pdf_files, data_dir)
        except FileNotFoundError as e:
            logger.error(str(e))
            return
        logger.info(f"Processing {len(pdf_files)} specified PDF files")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory: {os.path.abspath(output_dir)}")

    # Initialize PaperProcessor
    try:
        processor = PaperProcessor(
            pdf_dir=data_dir,
            mineru_dir=output_dir,
            llm_aid=llm_aid,
            max_download_period=poll_timeout,
        )
        logger.info("✓ PaperProcessor initialized successfully")
    except Exception as e:
        logger.exception(f"Failed to initialize PaperProcessor: {e}")
        return

    # Run the pipeline
    start_time = datetime.now()
    logger.info(f"Pipeline started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        results = processor.process_local_pdfs(
            pdf_files=pdf_files if not process_all else None,
            process_all=process_all,
            output_dir=output_dir,
            max_retries=max_retries,
            continue_on_error=continue_on_error,
            model_version=model_version,
            language=language,
            is_ocr=is_ocr,
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("Pipeline Results Summary")
        logger.info("=" * 80)
        logger.info(f"Total files: {results.get('total', 0)}")
        logger.info(f"Successful: {results.get('successful', 0)}")
        logger.info(f"Failed: {results.get('failed', 0)}")
        logger.info(f"Duration: {duration:.2f} seconds")

        if results.get("output_dir"):
            logger.info(f"Output directory: {results['output_dir']}")

        if results.get("errors"):
            logger.warning("\nErrors encountered:")
            for error in results["errors"]:
                logger.warning(f"  - {error.get('file', error.get('phase', 'unknown'))}: {error['error']}")

        logger.info("=" * 80)

        # Save summary if requested
        if save_summary:
            summary_path = os.path.join(
                output_dir, f"processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            summary_data = {
                **results,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "configuration": {
                    "all": process_all,
                    "pdf_files": specific_pdf_files,
                    "data_dir": data_dir,
                    "output_dir": output_dir,
                    "max_retries": max_retries,
                    "continue_on_error": continue_on_error,
                    "file_on_error": file_on_error,
                    "model_version": model_version,
                    "language": language,
                    "is_ocr": is_ocr,
                    "poll_timeout": poll_timeout,
                    "llm_aid": llm_aid,
                    "verbose": verbose,
                    "save_summary": save_summary,
                },
            }
            with open(summary_path, "w") as f:
                json.dump(summary_data, f, indent=2)
            logger.info(f"Processing summary saved to: {summary_path}")

        return 0 if results.get("failed", 0) == 0 else 1

    except Exception as e:
        logger.exception(f"Pipeline failed with error: {e}")
        return 1
    

def main():
    """Main entry point for local PDF parsing pipeline."""
    args = parse_args()

    # Configure verbose logging if requested
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # Log configuration
    logger.info("=" * 80)
    logger.info("Local PDF Parsing Pipeline - Starting")
    logger.info("=" * 80)
    logger.info(f"Configuration: {json.dumps(vars(args), indent=2)}")

    # Validate input: either --all or pdf_files must be specified, but not both
    if args.all and args.pdf_files:
        logger.error("Cannot specify both --all and specific PDF files")
        logger.error("Use either: --all OR file1.pdf file2.pdf ...")
        sys.exit(1)

    if not args.all and not args.pdf_files:
        logger.error("Must specify either --all or at least one PDF file")
        logger.error("Examples:")
        logger.error("  python local_pdf_parser.py --all")
        logger.error("  python local_pdf_parser.py paper1.pdf paper2.pdf")
        sys.exit(1)

    # Validate data directory exists
    if not os.path.isdir(args.data_dir):
        logger.error(f"Data directory does not exist: {args.data_dir}")
        logger.error("Please create it and add PDF files before running.")
        sys.exit(1)

    # Determine which PDFs to process
    if args.all:
        pdf_files = [f for f in os.listdir(args.data_dir) if f.lower().endswith(".pdf")]
        if not pdf_files:
            logger.error(f"No PDF files found in {args.data_dir}")
            sys.exit(1)
        logger.info(f"Found {len(pdf_files)} PDF files in {args.data_dir}")
    else:
        # Validate specified PDF files exist
        try:
            pdf_files = validate_pdf_files(args.pdf_files, args.data_dir)
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)
        logger.info(f"Processing {len(pdf_files)} specified PDF files")

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    logger.info(f"Output directory: {os.path.abspath(args.output_dir)}")

    # Initialize PaperProcessor
    try:
        processor = PaperProcessor(
            pdf_dir=args.data_dir,
            mineru_dir=args.output_dir,
            llm_aid=args.llm_aid,
            max_download_period=args.poll_timeout,
        )
        logger.info("✓ PaperProcessor initialized successfully")
    except Exception as e:
        logger.exception(f"Failed to initialize PaperProcessor: {e}")
        sys.exit(1)

    # Run the pipeline
    start_time = datetime.now()
    logger.info(f"Pipeline started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        results = processor.process_local_pdfs(
            pdf_files=pdf_files if not args.all else None,
            process_all=args.all,
            output_dir=args.output_dir,
            max_retries=args.max_retries,
            continue_on_error=args.continue_on_error,
            model_version=args.model_version,
            language=args.language,
            is_ocr=args.is_ocr,
        )

        # Report results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("Pipeline Results Summary")
        logger.info("=" * 80)
        logger.info(f"Total files: {results['total']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Duration: {duration:.2f} seconds")

        if results.get("output_dir"):
            logger.info(f"Output directory: {results['output_dir']}")

        if results.get("errors"):
            logger.warning("\nErrors encountered:")
            for error in results["errors"]:
                logger.warning(f"  - {error.get('file', error.get('phase', 'unknown'))}: {error['error']}")

        logger.info("=" * 80)

        # Save summary if requested
        if args.save_summary:
            summary_path = os.path.join(
                args.output_dir, f"processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            summary_data = {
                **results,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "configuration": vars(args),
            }
            with open(summary_path, "w") as f:
                json.dump(summary_data, f, indent=2)
            logger.info(f"Processing summary saved to: {summary_path}")

        # Exit with appropriate code
        sys.exit(0 if results["failed"] == 0 else 1)

    except Exception as e:
        logger.exception(f"Pipeline failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

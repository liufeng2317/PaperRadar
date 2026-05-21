# Local PDF Parser - Usage Guide

## Overview

The `local_pdf_parser.py` script provides a streamlined pipeline for processing local PDF files with MinerU. It automates the entire workflow: **upload → poll → download → extract → LLM enhance**.

## Quick Start

### Prerequisites

1. **MinerU Library**: Install MinerU and its dependencies
   ```bash
   pip install "mineru[all]" -U
   ```

2. **Environment Variables**: Configure `.env` file with required API keys
   ```bash
   # MinerU Cloud API
   MINERU_API_BASE=https://api.mineru.example.com
   MINERU_API_KEY=your_api_key_here

   # LLM for Title Optimization (optional, if llm-aid=True)
   PJLAB_API_KEY=your_llm_api_key
   PJLAB_API_BASE_URL=https://api.llm.example.com
   PJLAB_API_CHAT_MODEL=model_name

   # Optional: Enable table processing
   MINERU_VLM_TABLE_ENABLE=True
   ```

3. **PDF Files**: Place PDF files in the `data/` directory
   ```bash
   mkdir -p data/
   cp /path/to/your/pdfs/*.pdf data/
   ```

## Usage

### Basic Commands

#### Process All PDFs in `data/` Directory
```bash
python local_pdf_parser.py --all
```

#### Process Specific PDFs
```bash
python local_pdf_parser.py paper1.pdf paper2.pdf paper3.pdf
```

#### With Custom Output Directory
```bash
python local_pdf_parser.py --all --output-dir ./my_results
```

### Advanced Options

#### Configure Polling Timeout
```bash
# Default: 300 seconds (5 minutes)
python local_pdf_parser.py --all --poll-timeout 300

# Increase timeout for complex PDFs (10 minutes)
python local_pdf_parser.py --all --poll-timeout 600
```

**What is polling timeout?**
- Maximum time to wait for MinerU to finish processing PDFs
- Polling occurs every 5 seconds until all files are done/failed
- If timeout expires, pending files are marked as timed out

#### Disable LLM Enhancement (Faster Processing)
```bash
python local_pdf_parser.py --all --no-llm-aid
```

#### Increase Retry Attempts (Unstable Network)
```bash
python local_pdf_parser.py --all --max-retries 5
```

#### Stop on First Error (Strict Mode)
```bash
python local_pdf_parser.py --all --fail-on-error
```

#### Enable Verbose Logging (Debugging)
```bash
python local_pdf_parser.py --all --verbose
```

#### Save Processing Summary
```bash
python local_pdf_parser.py --all --save-summary
```

#### Change Processing Model
```bash
# Use pipeline model instead of VLM
python local_pdf_parser.py --all --model-version pipeline

# Disable OCR for born-digital PDFs
python local_pdf_parser.py --all --no-ocr

# Process Chinese PDFs
python local_pdf_parser.py --all --language zh
```

### Custom Data Directory
```bash
python local_pdf_parser.py --all --data-dir /path/to/pdfs --output-dir /path/to/results
```

## Pipeline Workflow

The automated pipeline executes in 4 phases:

### Phase 1/4: Upload
```
PDF files → MinerU Cloud API
└─> Creates batch task
└─> Generates signed URLs for each file
└─> Uploads PDFs to cloud storage
└─> Progress bar shows upload progress
```

### Phase 2/4: Poll for Completion
```
Polling Loop (every 5 seconds):
├─> Check API for file status
├─> File states:
│   ├─ "pending"      → Queued for processing
│   ├─ "running"      → Currently being processed
│   ├─ "converting"   → Format conversion in progress
│   ├─ "done" ✓       → Processing complete
│   └─ "failed" ✗     → Processing failed
└─> Exit when all files are done/failed or timeout
```

**Example Polling Timeline:**
```
00:00 - Upload complete, start polling
00:05 - Poll 1: paper.pdf=running
00:10 - Poll 2: paper.pdf=running
00:15 - Poll 3: paper.pdf=converting
00:20 - Poll 4: paper.pdf=done ✓
00:20 - All files complete! Proceeding to download...
```

### Phase 3/4: Download Results
```
MinerU Cloud → Local ZIP files
├─> Download each completed result
├─> Retry up to --max-retries times on failure
└─> Save to mineru_dir
```

### Phase 4/4: Extract and Enhance
```
ZIP files → Extract → LLM Enhancement
├─> Extract session folders (preserves structure)
├─> Load PDF images and model.json
├─> LLM optimizes title hierarchy
└─> Generate enhanced markdown
```

## Output Structure

Results are saved to the `output/` directory (or custom `--output-dir`):

```
output/
├── results_20250129_150400/                      # Timestamped batch folder
│   ├── session_uuid_1/                            # MinerU session folder
│   │   ├── {pdf_name}_origin.pdf                 # Original PDF (copied)
│   │   ├── {pdf_name}_model.json                 # MinerU raw output
│   │   ├── {pdf_name}.md                          # LLM-enhanced markdown ✓
│   │   └── images/
│   │       ├── *.jpg                               # Extracted figures
│   │       └── *.png
│   ├── session_uuid_2/
│   │   ├── {pdf_name}_origin.pdf
│   │   ├── {pdf_name}_model.json
│   │   ├── {pdf_name}.md
│   │   └── images/
│   │       └── ...
│   └── ...
└── processing_summary_20250129_150400.json        # Processing summary (if --save-summary)
```

**Session Folder Contents:**
- `{pdf_name}_origin.pdf`: Copy of your original PDF
- `{pdf_name}_model.json`: Raw MinerU parsing result (blocks, layout, etc.)
- `{pdf_name}.md`: **Final enhanced markdown** with:
  - Optimized heading hierarchy (via LLM)
  - Extracted text and tables
  - Embedded image references
  - Clean, structured content
- `images/`: All figures, tables, and visual elements extracted from PDF

## Processing Summary

When using `--save-summary`, a JSON file is created with detailed results:

```json
{
  "total": 10,
  "successful": 9,
  "failed": 1,
  "output_dir": "/path/to/output/results_20250129_150400",
  "start_time": "2025-01-29T15:04:00",
  "end_time": "2025-01-29T15:10:30",
  "duration_seconds": 390.5,
  "errors": [
    {
      "file": "paper3.pdf",
      "error": "MinerU timeout after 300s (final state: running)"
    }
  ],
  "configuration": {
    "all": true,
    "max_retries": 3,
    "llm_aid": true,
    "poll_timeout": 300,
    ...
  }
}
```

## Error Handling

The pipeline has multiple levels of error handling:

### 1. Per-Phase Retry (Exponential Backoff)
- **Upload phase**: Retries up to `--max-retries` times (1s, 2s, 4s, 8s...)
- **Poll phase**: Retries API errors with 5-second delays
- **Download phase**: Each file retries up to `--max-retries` times
- **Extract phase**: Depends on `--continue-on-error` setting

### 2. Per-File Error
- Individual file errors are logged with file name and error message
- Pipeline continues with remaining files (if `--continue-on-error`)
- Failed files tracked in summary

### 3. API-Level Resilience
- Network errors: Automatic retry after 5 seconds
- Invalid responses: Skip current poll, retry in 5 seconds
- Parse errors: Log warning, retry in 5 seconds
- Timeouts: Files marked as timed out with final state

### 4. Pipeline-Level
- Catastrophic errors caught and logged
- Temporary directories cleaned up on exit
- Partial results preserved when possible

## Logging

Logs are saved to `./logs/local_pdf_parser/pipeline_*.log` with:

- **Phase markers**: `[Phase 1/4]`, `[Phase 2/4]`, etc.
- **Progress updates**: File counts, percentages, rates
- **File status**: `{filename} ✓ Processing complete`, `{filename} ✗ Failed`
- **Error messages**: Detailed errors with context
- **Final summary**: Success/failure counts, duration

**Example Log Output:**
```
2026-01-29 15:43:47 | INFO | ================================================================================
2026-01-29 15:43:47 | INFO | Local PDF Parsing Pipeline - Starting
2026-01-29 15:43:47 | INFO | Found 1 PDF files in data/
2026-01-29 15:43:47 | INFO | ✓ PaperProcessor initialized successfully
2026-01-29 15:43:47 | INFO | [Phase 1/4] Uploading 1 PDFs to MinerU...
2026-01-29 15:43:50 | INFO | s43017-023-00438-5.pdf ✓ upload success
2026-01-29 15:43:50 | INFO | [Phase 2/4] Polling for task completion...
2026-01-29 15:43:55 | INFO | s43017-023-00438-5.pdf - state: running
2026-01-29 15:44:00 | INFO | s43017-023-00438-5.pdf - state: converting
2026-01-29 15:44:15 | INFO | s43017-023-00438-5.pdf ✓ Processing complete
2026-01-29 15:44:15 | INFO | [Phase 3/4] Downloading MinerU results...
2026-01-29 15:44:20 | INFO | [Phase 4/4] Extracting and enhancing results...
2026-01-29 15:44:35 | INFO | ✓ Extracted to: output/results_.../session_...
2026-01-29 15:44:35 | INFO | ✓ Processing complete: 1/1 successful
2026-01-29 15:44:35 | INFO | ✓ Results saved to: output/results_20250129_154435
```

Use `--verbose` to see debug-level logs in the console.

## Exit Codes

- **0**: All files processed successfully
- **1**: One or more files failed (check logs and summary)

## Examples

### Example 1: Process All PDFs with Default Settings
```bash
python local_pdf_parser.py --all
```

**What happens:**
1. Scans `data/` directory for PDF files
2. Uploads all PDFs to MinerU
3. Polls every 5 seconds for completion (up to 5 minutes)
4. Downloads results when ready
5. Extracts and generates LLM-enhanced markdown
6. Saves to `output/results_TIMESTAMP/`

### Example 2: Process Specific Files with Custom Options
```bash
python local_pdf_parser.py \
  paper1.pdf \
  paper2.pdf \
  --max-retries 5 \
  --poll-timeout 600 \
  --no-llm-aid \
  --save-summary \
  --verbose
```

**Options breakdown:**
- `--max-retries 5`: Retry failed operations 5 times
- `--poll-timeout 600`: Wait up to 10 minutes for processing
- `--no-llm-aid`: Skip LLM title optimization (faster)
- `--save-summary`: Export processing details to JSON
- `--verbose`: Show debug logs

### Example 3: Production Batch Processing
```bash
# Create log directory
mkdir -p logs

# Run with all safety options in background
nohup python local_pdf_parser.py \
  --all \
  --max-retries 5 \
  --poll-timeout 600 \
  --continue-on-error \
  --save-summary \
  > logs/run_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Monitor progress
tail -f logs/local_pdf_parser/pipeline_*.log
```

### Example 4: Quick Test with Short Timeout
```bash
# For testing - timeout after 60 seconds
python local_pdf_parser.py test.pdf --poll-timeout 60 --verbose
```

## Troubleshooting

### Issue: "Data directory does not exist"
**Solution**: Create the `data/` directory and add PDF files
```bash
mkdir -p data/
cp /path/to/pdfs/*.pdf data/
```

### Issue: "No PDF files found in data/"
**Solution**: Ensure PDF files have `.pdf` extension (case-insensitive)

### Issue: "Must specify either --all or at least one PDF file"
**Solution**: Provide either `--all` flag or list specific PDF files
```bash
# Correct:
python local_pdf_parser.py --all
python local_pdf_parser.py file1.pdf file2.pdf

# Incorrect:
python local_pdf_parser.py
```

### Issue: "MinerU API connection failed"
**Solutions**:
1. Check your `.env` file has correct `MINERU_API_BASE` and `MINERU_API_KEY`
2. Verify network connectivity to MinerU API
3. Check if API service is operational
4. Try increasing `--max-retries` for unstable networks

### Issue: "LLM enhancement failed"
**Solutions**:
1. Check `.env` has correct LLM API credentials
2. Use `--no-llm-aid` to skip LLM enhancement
3. Check LLM service status

### Issue: "PDF processing timeout"
**Solutions**:
1. Increase `--poll-timeout` (e.g., `--poll-timeout 600` for 10 minutes)
2. Check if PDF is very large or complex
3. Verify MinerU service is operational
4. Check logs for final state when timeout occurred

### Issue: Files stuck in "running" or "pending" state
**Diagnosis**:
```bash
# Check logs for polling activity
tail -100 logs/local_pdf_parser/pipeline_*.log | grep "state:"

# Look for final state messages
grep "Timed out" logs/local_pdf_parser/pipeline_*.log
```

**Possible causes**:
- MinerU backend overloaded
- PDF too complex for current model
- Processing queue too long

**Solutions**:
- Increase `--poll-timeout`
- Try processing at off-peak hours
- Contact MinerU support if issue persists

## Programmatic Usage

You can also use the pipeline programmatically:

```python
from paper_processor import PaperProcessor

# Initialize processor with custom timeout
processor = PaperProcessor(
    pdf_dir="data/",
    mineru_dir="output/",
    llm_aid=True,
    max_download_period=600  # Custom timeout (10 minutes)
)

# Run pipeline
results = processor.process_local_pdfs(
    process_all=True,
    max_retries=3,
    continue_on_error=True,
    model_version="vlm",
    language="en",
    is_ocr=True
)

# Check results
print(f"Processed: {results['successful']}/{results['total']}")
print(f"Failed: {results['failed']}")
print(f"Output: {results['output_dir']}")

# Check errors if any
if results['errors']:
    for error in results['errors']:
        print(f"Error: {error}")
```

## Backward Compatibility

The original `paper_processor.py` CLI remains unchanged and fully functional:

```bash
# Original multi-step workflow still works
python paper_processor.py --parse --mineru-dir ./output
python paper_processor.py --download-mineru --mineru-task-log ./logs/task.json
```

## Performance Tips

1. **Polling Interval**: Fixed at 5 seconds (optimal for most cases)
2. **Batch Size**: The pipeline processes all PDFs in one batch (up to MinerU's limit of 200)
3. **Parallel Processing**: MinerU processes PDFs in parallel on the server
4. **LLM Skip**: Use `--no-llm-aid` for 30-50% faster processing
5. **Network**: Stable connection reduces retry delays
6. **Timeout Tuning**:
   - Simple PDFs: 60-120 seconds sufficient
   - Complex PDFs: May need 300-600 seconds
   - Very large/complex PDFs: Consider 600+ seconds

## Understanding Polling Behavior

### How Polling Works (Fixed Implementation):

```python
# Polling loop runs every 5 seconds
while files_still_processing and not timeout:
    # 1. Fetch FRESH status from MinerU API
    api_response = requests.get(batch_status_url)

    # 2. Check each file's status
    for file in pending_files:
        if file.state == "done":
            mark_complete(file)
        elif file.state == "failed":
            mark_failed(file)
        else:
            # Still processing (pending/running/converting)
            keep_pending(file)

    # 3. Wait 5 seconds before next poll
    time.sleep(5)
```

### Key Characteristics:

✅ **Fresh Data**: Each poll gets updated status from API
✅ **Efficient**: 5-second interval balances responsiveness vs API load
✅ **Resilient**: Automatic retry on network/API errors
✅ **Informative**: Progress bars and log messages show real-time status
✅ **Timeout Safe**: Won't hang forever, respects `--poll-timeout`

## MinerU File States

Understanding what each state means:

- **`waiting-file`**: File uploaded, waiting to be queued
- **`pending`**: Queued for processing, waiting for available worker
- **`running`**: Actively being processed by MinerU
- **`converting`**: Format conversion in progress
- **`done`**: ✓ Processing complete successfully
- **`failed`**: ✗ Processing failed (check error message)

Typical progression for a successful file:
```
pending → running → converting → done ✓
```

## Support

For issues or questions:
1. Check logs in `./logs/local_pdf_parser/`
2. Use `--verbose` flag for detailed debugging
3. Review processing summary JSON (if `--save-summary` was used)
4. Verify `.env` configuration
5. Check MinerU service status
6. Review error messages in logs for specific file failures

## Advanced: Session Structure Details

Each MinerU session folder contains:

```
session_uuid/
├── {pdf_name}_origin.pdf      # Your original PDF (copied for reference)
├── {pdf_name}_model.json      # MinerU's structured output
│   ├─ "pdf_info": {...}        # Document structure
│   ├─ "layouts": [...]        # Page layouts
│   └─ "pages": [...]          # Page contents (blocks, text, images)
└── images/                     # Extracted visual elements
    ├── fig_1.jpg              # Figures and tables
    ├── fig_2.png
    └── ...
```

The `model.json` file is the foundation for:
- **Markdown generation**: Structure and content
- **LLM enhancement**: Raw text and layout for title optimization
- **Image extraction**: References to extracted images

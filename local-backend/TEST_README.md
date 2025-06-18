# Markdown Editor Comprehensive Tests

This directory contains comprehensive tests for the Markdown Editor MCP Server functionality.

## Quick Start

```bash
# 1. Navigate to local-backend directory
cd local-backend

# 2. Create and activate virtual environment (recommended)
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# 3. (Optional) Set up API keys for full testing
export UNSPLASH_ACCESS_KEY=your_unsplash_api_key_here

# 4. Run the test suite
python run_tests.py
```

## API Key Setup (Optional)

For complete testing, you can set up these API keys:

### Unsplash Photos
- Get a free API key: https://unsplash.com/developers
- Set environment variable: `export UNSPLASH_ACCESS_KEY=your_key_here`
- **Without this**: Photo download tests will be skipped (other tests still work)

**Note**: Tests will run fine without API keys, but photo-related functionality will be skipped.

## What Gets Tested

### 📝 Document Creation
- Basic markdown document creation
- File path handling in workspace

### 📷 Photo Search & Download
Tests all photo sizes with real Unsplash API:
- **thumbnail**: ~150px wide (for small previews)
- **small**: ~400px wide (for sidebars)
- **regular**: ~1080px wide (default, good balance)
- **large**: ~2000px wide (for hero images)
- **full**: Original resolution

### 📊 Chart Creation
- Bar charts with QuickChart API
- File size and dimension verification
- Workspace integration

### 📋 Table Creation
- Multiple table themes (professional, modern, minimal)
- Hamburg startup events sample data
- Table extraction functionality

### 🖼️ Image Integration
- Adding photos to documents
- Adding charts to documents
- Path resolution testing

### 👁️ Live Preview
- Local server startup
- Port configuration

### 🔄 Document Conversion
- HTML conversion
- Text conversion
- File size verification

### 🔍 Path Resolution
- Workspace file finding
- Filesystem compatibility
- Error handling

### 📋 Document Analysis
- Header extraction
- Section analysis

## Photo Size Guide for Agents

When using `search_and_download_photo`, specify the `size` parameter:

```python
# For thumbnails or small UI elements
result = await search_and_download_photo_tool(
    query="business meeting", 
    size="small"
)

# For main content images (recommended default)
result = await search_and_download_photo_tool(
    query="business meeting", 
    size="regular"
)

# For hero images or detailed photos
result = await search_and_download_photo_tool(
    query="business meeting", 
    size="large"
)
```

## Table Themes Available

- **professional**: Clean business look
- **modern**: Contemporary styling  
- **minimal**: Simple, clean design

## Files Created During Testing

All test files are created in a temporary workspace directory:
- Photos: `business_meeting_{size}.jpg`
- Charts: `hamburg_startups_chart.png`
- Tables: `events_table_{theme}.md`
- Documents: `test_newsletter.md`
- Conversions: `test_output.{format}`

## Dependencies

The test automatically checks and can install:
- `aiohttp` - For async HTTP requests
- `requests` - For synchronous HTTP requests  
- `pillow` - For image processing
- `pandas` - For data handling

## Troubleshooting

### Import Errors
Make sure you're running from the `local-backend` directory and the MCP server modules are available.

### API Failures
Photo download tests require internet connection and Unsplash API access. Chart tests require QuickChart API access.

### Permission Errors
Ensure write permissions to the temp directory for file creation tests.

## Understanding Test Results

- ✅ **Green checkmarks**: Test passed
- ❌ **Red X marks**: Test failed
- File sizes and dimensions are shown for verification
- Final summary shows pass/fail statistics

The test workspace directory is preserved after testing so you can inspect the generated files. 
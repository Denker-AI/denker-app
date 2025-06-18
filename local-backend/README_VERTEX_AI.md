# Anthropic Claude Models via Google Vertex AI

This implementation allows you to use Anthropic Claude models (Haiku and Sonnet 3.7) through Google Vertex AI instead of the direct Anthropic API, while maintaining exactly the same business logic and query processing.

## Benefits of Using Vertex AI

1. **Cost Optimization**: Potentially lower costs through Google Cloud's pricing
2. **Unified Billing**: Single Google Cloud bill for all AI services
3. **Enterprise Features**: Access to Google Cloud's enterprise security and compliance features
4. **Regional Availability**: Access Claude models in specific Google Cloud regions
5. **Integration**: Better integration with existing Google Cloud infrastructure

## Quick Setup

### 1. Install Dependencies

```bash
pip install 'anthropic[vertex]'
```

### 2. Set Environment Variables

**Option A: Using environment variables**
```bash
export USE_VERTEX_ANTHROPIC=true
export VERTEX_PROJECT_ID=your-google-cloud-project-id
export VERTEX_REGION=us-east5
```

**Option B: Copy the example config**
```bash
cp vertex_config_example.env .env
# Edit .env with your project details
```

### 3. Authenticate with Google Cloud

```bash
# Install Google Cloud SDK if not already installed
# Then authenticate:
gcloud auth application-default login
```

### 4. Start the Application

No code changes needed! The application will automatically use Vertex AI when `USE_VERTEX_ANTHROPIC=true`.

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `USE_VERTEX_ANTHROPIC` | `false` | Set to `true` to enable Vertex AI |
| `VERTEX_PROJECT_ID` | Required | Your Google Cloud project ID |
| `VERTEX_REGION` | `us-east5` | Google Cloud region for Claude models |

## Available Claude Models on Vertex AI

The following models are automatically mapped:

| Standard Model Name | Vertex AI Format | Description |
|-------------------|------------------|-------------|
| `claude-3-7-sonnet-20250219` | `claude-3-7-sonnet@20250219` | Latest Sonnet model |
| `claude-3-5-haiku-20241022` | `claude-3-5-haiku@20241022` | Latest Haiku model |
| `claude-3-5-sonnet-v2-20241022` | `claude-3-5-sonnet-v2@20241022` | Sonnet v2 model |

Model names are automatically converted from standard format to Vertex AI format.

## Switching Between APIs

### Switch to Vertex AI
```bash
export USE_VERTEX_ANTHROPIC=true
export VERTEX_PROJECT_ID=your-project-id
```

### Switch back to Direct Anthropic API
```bash
export USE_VERTEX_ANTHROPIC=false
```

## Available Regions

Claude models are available in these Google Cloud regions:
- `us-east5` (Default)
- `europe-west1`
- `asia-pacific1`

## Implementation Details

The integration works by:

1. **Client Selection**: The `FixedAnthropicAugmentedLLM` class automatically selects between direct Anthropic API and Vertex AI based on the `USE_VERTEX_ANTHROPIC` environment variable.

2. **Model Name Conversion**: Standard Anthropic model names are automatically converted to Vertex AI format (e.g., `-20250219` becomes `@20250219`).

3. **Authentication**: Uses Google Cloud Application Default Credentials (ADC) for authentication.

4. **Transparent Integration**: No changes needed to existing business logic, tool calling, or structured generation.

## Troubleshooting

### Common Issues

1. **Missing Vertex AI Package**
   ```
   ImportError: No module named 'anthropic.vertex'
   ```
   **Solution**: Install with `pip install 'anthropic[vertex]'`

2. **Authentication Error**
   ```
   google.auth.exceptions.DefaultCredentialsError
   ```
   **Solution**: Run `gcloud auth application-default login`

3. **Project ID Not Set**
   ```
   ValueError: VERTEX_PROJECT_ID environment variable is required
   ```
   **Solution**: Set `VERTEX_PROJECT_ID` environment variable

4. **Region Not Available**
   ```
   API not available in region
   ```
   **Solution**: Use a supported region (us-east5, europe-west1, or asia-pacific1)

### Verification

To verify which API is being used, check the logs for:
- `[FixedAnthropicAugmentedLLM] Configured to use Vertex AI` (when using Vertex AI)
- `[FixedAnthropicAugmentedLLM] Configured to use direct Anthropic API` (when using direct API)

## Code Changes Made

The implementation adds Vertex AI support to the existing `FixedAnthropicAugmentedLLM` class in `coordinator_agent.py`:

1. **Environment Configuration**: Added variables to control which API to use
2. **Client Selection**: Added methods to create appropriate Anthropic client
3. **Model Conversion**: Added automatic model name format conversion
4. **Transparent Integration**: Updated `generate` and `generate_structured` methods to use the selected client

The changes maintain full backward compatibility and require no modifications to existing business logic. 
# Vertex AI + Anthropic Claude Integration Guide

This guide provides comprehensive instructions for setting up and using Anthropic Claude models via Google Cloud Vertex AI in your application.

## Prerequisites

1. A Google Cloud project with Vertex AI API enabled
2. The necessary permissions configured for your service account
3. Access to Anthropic Claude models via Vertex AI (requires special permissions and entitlements)
4. Sufficient quota for the Anthropic models you plan to use

## 1. Setting Up Your Service Account Key

1. **Create a service account** in your Google Cloud project with the following roles:
   - `roles/aiplatform.user`
   - `roles/serviceusage.serviceUsageConsumer`

2. **Create a JSON key file** for this service account and securely store it in one of these locations:
   - `/app/vertexai.json` (in Docker)
   - `backend/vertexai.json` (in your project directory)

3. **Set environment variable** to point to your key file:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/keyfile.json
   ```

## 2. Configuring the Application

Update your configuration file `backend/mcp_local/mcp_agent.config.yaml` with the following settings:

```yaml
vertex:
  project_id: "your-gcp-project-id"  # Required: Your GCP project ID
  location: "europe-west1"           # Supported regions: europe-west1 or europe-west4
  anthropic_model: "claude-3-7-sonnet@20250219"  # Confirmed working model format
  service_account_key_path: "/app/vertexai.json"  # Path to your key file
```

## 3. Understanding Model Access and Quotas

### Model Access

**Important:** To use Claude models, your Google Cloud project must be explicitly granted access. These errors indicate access issues:

```
Project `project-id` is not allowed to use Publisher Model `projects/project-id/locations/europe-west4/publishers/anthropic/models/claude-3-haiku@20240307`
```

### Quota Limits

Once you have access, you may encounter quota limits:

```
429 Quota exceeded for aiplatform.googleapis.com/generate_content_requests_per_minute_per_project_per_base_model with base model: anthropic-claude-3-7-sonnet
```

This indicates your project has access to the model but is hitting the rate limit. You can request a quota increase at: https://cloud.google.com/vertex-ai/docs/generative-ai/quotas-genai

### How to Request Access and Quota Increases

1. Contact your Google Cloud representative or Anthropic representative
2. Request for your project to be whitelisted for Anthropic Claude models
3. Specify which models you need access to (e.g., claude-3-7-sonnet)
4. Request appropriate quota limits based on your expected usage
5. Specify which regions you need access in (europe-west1 and/or europe-west4)

## 4. Testing Your Setup

Once you have the necessary permissions, you can test your setup using one of the provided test scripts:

### Direct Test Script (Recommended for Initial Verification)

```bash
python /app/test_claude_vertex.py
```

This script directly tests the Vertex AI connection to the Claude 3.7 Sonnet model with rate limit handling.

### Interactive Test Script

```bash
python /app/test_vertex_anthropic_docker_interactive.py
```

This script provides an interactive interface for testing the VertexAnthropicAugmentedLLM with custom prompts.

## 5. Regions and Availability

We've tested both `europe-west1` and `europe-west4` regions, and both should work with Claude models. You may want to test both to see which works best for your use case:

- The quota limits may be different in each region
- Model availability may vary between regions
- Response times might differ depending on your location relative to the region

## 6. Correct Model Name Format

Based on our extensive testing, we have confirmed these details about model naming:

1. **Base Model Name**: The Vertex AI base model is `anthropic-claude-3-7-sonnet`
   - This is what appears in quota error messages
   - This is not the direct model name you should use

2. **Working Model Formats**:
   - `claude-3-7-sonnet@20250219` - This format works and is preferred for simplicity
   - `publishers/anthropic/models/claude-3-7-sonnet` - This publisher format also works

3. **Non-working Model Formats**:
   - `anthropic-claude-3-7-sonnet` - This base model name doesn't work directly
   - `anthropic-claude-3-7-sonnet@20250219` - This hybrid format doesn't work

In most cases, you should use `claude-3-7-sonnet@20250219` as your model name.

## 7. Integration with Your Application

Once your setup is verified, the `VertexAnthropicAugmentedLLM` class can be attached to your agent:

```python
from mcp_local.llm.vertex_anthropic_llm import VertexAnthropicAugmentedLLM

# Set a dummy API key for the Anthropic client
os.environ['ANTHROPIC_API_KEY'] = 'dummy_key_for_vertex_ai'

# Attach the LLM to your agent
llm = await agent.attach_llm(VertexAnthropicAugmentedLLM)

# Generate a response
response = await llm.generate_str(
    message="Your prompt here",
    request_params=RequestParams(temperature=0.2, max_tokens=1024)
)
```

## 8. Troubleshooting

### Access Issues

- **Error: "Project not allowed to use Publisher Model"** - Your GCP project needs to be whitelisted for access to Claude models. Contact Google Cloud support.

- **Error: "Publisher Model not found"** - The model name or version might be incorrect, or the model isn't available in the specified region.

### Quota Issues

- **Error: "429 Quota exceeded"** - You're hitting rate limits. Request quota increases via the Google Cloud Console.
  - The error message will specify the base model: `anthropic-claude-3-7-sonnet`
  - This confirms you have access to the model but need higher quotas

### Authentication Issues

- **Error: "NoneType object has no attribute 'api_key'"** - The VertexAnthropicAugmentedLLM requires a dummy ANTHROPIC_API_KEY environment variable even when using Vertex AI:
  ```python
  os.environ['ANTHROPIC_API_KEY'] = 'dummy_key_using_vertex_ai'
  ```

- **Error: "Credentials object has no attribute 'get_access_token'"** - Make sure your service account key file is correctly formatted and has the necessary permissions.

## 9. Best Practices

1. **Security**: Store your service account key securely and restrict its permissions
2. **Region Selection**: Test both europe-west1 and europe-west4 to determine which works best
3. **Error Handling**: Implement robust error handling for API failures, including rate limiting
4. **Monitoring**: Set up monitoring for API quotas and usage
5. **Cost Management**: Be aware of Vertex AI pricing for model usage
6. **Retry Logic**: Implement exponential backoff for rate limit errors (as shown in our test script)

## 10. Important Reminder

To successfully use Claude models through Vertex AI:
1. Your project **must** have the appropriate entitlements set up through Google Cloud
2. You **must** use the correct model format: `claude-3-7-sonnet@20250219`
3. The underlying base model is `anthropic-claude-3-7-sonnet` (for quota purposes)
4. You need sufficient quotas for your expected usage
5. You should set a dummy API key when using the VertexAnthropicAugmentedLLM wrapper 
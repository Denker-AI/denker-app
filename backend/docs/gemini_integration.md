# Gemini Integration

This document describes how to use the Gemini 2.0 Flash model in the Denker application.

## Overview

Denker integrates with Google's Gemini 2.0 Flash model through Vertex AI. This integration allows the application to generate text, answer questions, and perform other natural language processing tasks.

## Setup

1. **Environment Variables**

   Make sure the following environment variables are set in your `.env` file:

   ```
   VERTEX_AI_PROJECT=your-project-id
   VERTEX_AI_LOCATION=your-location
   VERTEX_AI_ENABLED=True
   ```

2. **Required Packages**

   The following packages are required for the Gemini integration:

   ```
   google-cloud-aiplatform
   vertexai
   ```

   Install them using pip:

   ```bash
   pip install google-cloud-aiplatform vertexai
   ```

3. **Authentication**

   Ensure you have the necessary Google Cloud credentials set up. You can authenticate using:

   ```bash
   gcloud auth application-default login
   ```

## API Endpoints

### Generate Text

Endpoint: `POST /api/v1/agents/generate-text`

This endpoint generates text using the Gemini 2.0 Flash model.

**Request Body:**

```json
{
  "prompt": "Your prompt here"
}
```

**Response:**

```json
{
  "text": "Generated text response"
}
```

### Gemini Agent

Endpoint: `POST /api/v1/agents/gemini`

This endpoint provides a more comprehensive integration with the Gemini model, including logging and tracking.

**Request Body:**

```json
{
  "prompt": "Your prompt here",
  "max_tokens": 1024,
  "temperature": 0.2
}
```

**Response:**

```json
{
  "query_id": "unique-query-id",
  "text": "Generated text response",
  "status": "success"
}
```

## Usage in Code

You can use the Gemini service in your code by importing the `vertex_ai_service` singleton:

```python
from services.vertex_ai import vertex_ai_service

# Generate text with Gemini
response = vertex_ai_service.generate_text_with_gemini(
    prompt="Your prompt here",
    max_tokens=1024,
    temperature=0.2
)
```

## Testing

You can test the Gemini integration using the provided test script:

```bash
python test_gemini.py
```

This script will initialize Vertex AI, create a Gemini model, and generate a response to a test prompt.

## Frontend Integration

A React component is provided for testing the Gemini integration:

```jsx
import GeminiTest from './components/GeminiTest';

function App() {
  return (
    <div className="App">
      <GeminiTest />
    </div>
  );
}
```

## Troubleshooting

If you encounter issues with the Gemini integration, check the following:

1. Ensure your Google Cloud project has the Vertex AI API enabled.
2. Verify that you have the necessary permissions to access Vertex AI.
3. Check that your authentication credentials are valid.
4. Look for error messages in the application logs.

## References

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Gemini API Documentation](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
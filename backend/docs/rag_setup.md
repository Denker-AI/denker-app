# Retrieval-Augmented Generation (RAG) Setup

This document describes how to set up and use Retrieval-Augmented Generation (RAG) with Qdrant in the Denker application.

## What is RAG?

Retrieval-Augmented Generation (RAG) is a technique that enhances language models by retrieving relevant information from a knowledge base before generating a response. This helps the LLM provide more accurate, up-to-date, and contextually relevant answers.

## Setup Process

### 1. Deploy Qdrant

If you don't already have a Qdrant instance, you can deploy one using the provided script:

```bash
# Make the deployment script executable
chmod +x deploy_qdrant.sh

# Run the deployment script
./deploy_qdrant.sh
```

This will:
- Create a VPC and subnet if needed
- Set up firewall rules
- Deploy a Qdrant instance in Google Cloud
- Provide you with the internal IP of the Qdrant server

### 2. Set Up SSH Tunnels

Update your `setup_tunnels.sh` script with the Qdrant private IP:

```bash
# Run the tunnels script
./setup_tunnels.sh
```

This establishes an SSH tunnel to your Qdrant instance, making it accessible at `localhost:6333`.

### 3. Initialize Qdrant Collection

Create a collection in Qdrant to store your vector embeddings:

```bash
python scripts/setup_qdrant.py --url http://localhost:6333
```

### 4. Load Sample Data

Load some sample data to test the RAG functionality:

```bash
python scripts/load_qdrant_data.py --url http://localhost:6333 --sample
```

You can also load your own data by creating a JSON file with the following structure:

```json
[
  {
    "text": "This is some information to be stored in the knowledge base",
    "metadata": {
      "source": "documentation",
      "category": "product_info",
      "timestamp": "2025-04-25T12:34:56.789Z"
    }
  },
  {
    "text": "Here is another piece of information",
    "metadata": {
      "source": "user_guide",
      "category": "how_to",
      "timestamp": "2025-04-26T10:11:12.131Z"
    }
  }
]
```

Then load it with:

```bash
python scripts/load_qdrant_data.py --url http://localhost:6333 --file your_data.json
```

### 5. Configure the Backend

Ensure that your `.env` file has the correct Qdrant configuration:

```
QDRANT_URL=http://localhost:6333
COLLECTION_NAME=denker_embeddings
QDRANT_ENABLED=True
```

### 6. Start the Backend

Finally, start the backend with Docker Compose:

```bash
docker-compose -f docker-compose.dev.yml up --build
```

## How It Works

1. **Embedding Generation**: Text chunks are converted to embeddings using a vector embedding model (Vertex AI).
2. **Vector Storage**: These embeddings are stored in Qdrant along with the original text and metadata.
3. **Query Process**: When a user asks a question:
   - The question is converted to an embedding
   - Similar embeddings are retrieved from Qdrant
   - The original text from those embeddings is used to augment the model's context
   - The model generates a response based on both its training data and the retrieved context

## Qdrant MCP Server Tools

The Qdrant MCP server provides two main tools:

1. **qdrant-store**: Store information in the vector database
   ```
   Input: 
   - information (string): Text to store
   - metadata (object): Optional metadata
   ```

2. **qdrant-find**: Retrieve relevant information
   ```
   Input:
   - query (string): Query to search for
   Output: Relevant documents from the database
   ```

## Using RAG in Conversations

When conversing with Denker, the RAG system works automatically in the background. The CoordinatorAgent evaluates whether to use RAG based on the complexity of the query.

For complex questions that might benefit from retrieval, the RAG agent is invoked to find relevant information before the model generates a response.

## Troubleshooting

### Connection Issues

If you have issues connecting to Qdrant:

1. Check if the SSH tunnel is active:
   ```bash
   netstat -an | grep 6333
   ```

2. Verify your Qdrant server is running:
   ```bash
   curl http://localhost:6333/collections
   ```

### Vector Search Issues

If vector search isn't working:

1. Verify your collection exists:
   ```bash
   curl http://localhost:6333/collections/denker_embeddings
   ```

2. Check that you have data in your collection:
   ```bash
   curl http://localhost:6333/collections/denker_embeddings/points/count
   ```

3. Make sure your embedding service is working correctly. 
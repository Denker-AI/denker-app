this.ws.onmessage = (event) => {
  // --- ADDED: Handle raw ping --- 
  if (event.data === 'ping') {
    console.log(`[${this.logPrefix}] Received ping from server.`);
    // Optional: Send pong back if needed by server protocol
    // this.ws?.send(JSON.stringify({ type: 'pong' }));
    return; // Don't try to parse ping as JSON
  }
  // --- END ADDED ---

  try {
    const data = JSON.parse(event.data);
    this.log(`Received message: ${JSON.stringify(data).substring(0, 100)}...`);
    
    // ... (rest of existing JSON message handling) ...

  } catch (error) {
     this.error(`Error parsing WebSocket message for ${this.queryId}: ${error instanceof Error ? error.toString() : String(error)}`);
     this.log(`Raw message data: ${event.data}`); // Log raw data on error
  }
}; 
/**
 * Browser Action Handler
 * 
 * Listens for WebSocket messages with update_type 'browser_action' and opens the specified URLs.
 * Used by features like markdown live preview that need to open content in the browser.
 */

/**
 * Initialize browser action event listeners
 */
export function initBrowserActionHandler() {
  // Listen for the general MCP update events from the WebSocket
  window.addEventListener('mcp-update', (event: any) => {
    const data = event.detail;
    
    // Check if this is a browser action
    if (data && data.update_type === 'browser_action') {
      handleBrowserAction(data);
    }
  });
  
  console.log('Browser action handler initialized');
}

/**
 * Handle browser action WebSocket messages
 */
function handleBrowserAction(data: any) {
  try {
    console.log('Handling browser action:', data);
    
    // Extract URL from the data
    const url = data.data?.url;
    if (!url) {
      console.error('Browser action missing URL');
      return;
    }
    
    // Open the URL in a new tab/window
    window.open(url, '_blank');
    console.log(`Opened URL in browser: ${url}`);
  } catch (error) {
    console.error('Error handling browser action:', error);
  }
}

// Export default initialize function to be called from main
export default initBrowserActionHandler; 
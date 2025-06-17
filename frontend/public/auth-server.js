// Auth server implementation for handling Auth0 callbacks in production mode
const http = require('http');
const url = require('url');

/**
 * Creates and starts an HTTP server to handle Auth0 callbacks in production mode
 * 
 * @param {object} options Configuration options
 * @param {number} options.port Port number to listen on (default: 8123)
 * @param {Function} options.onCallback Callback function when Auth0 redirects with code/state
 * @returns {http.Server} The HTTP server instance
 */
function createAuthServer(options = {}) {
  const { 
    port = 8123,
    onCallback = () => {}
  } = options;

  console.log(`🔒 Setting up Auth0 callback server on port ${port}`);
  
  const server = http.createServer((req, res) => {
    const urlParts = url.parse(req.url, true);
    const { pathname, query } = urlParts;
    
    console.log('👁️ Auth callback received at:', pathname);
    
    // Check if this is an Auth0 callback request
    if (pathname.startsWith('/callback')) {
      const { code, state, error, error_description } = query;
      
      if (error) {
        console.error('❌ Auth0 callback error:', error, error_description);
        res.writeHead(400, { 'Content-Type': 'text/html' });
        res.end(`<html>
          <head>
            <title>Authentication Error</title>
            <meta http-equiv="Content-Security-Policy" content="script-src 'self' 'unsafe-inline';">
          </head>
          <body>
            <h1>Authentication Error</h1>
            <p>${error}: ${error_description || 'No description provided'}</p>
            <p>Please close this window and try again.</p>
          </body>
        </html>`);
        return;
      }
      
      if (!code || !state) {
        console.error('❌ Missing required Auth0 parameters');
        res.writeHead(400, { 'Content-Type': 'text/html' });
        res.end(`<html>
          <head>
            <title>Invalid Request</title>
            <meta http-equiv="Content-Security-Policy" content="script-src 'self' 'unsafe-inline';">
          </head>
          <body>
            <h1>Invalid Authentication Request</h1>
            <p>Missing required parameters. Please close this window and try again.</p>
          </body>
        </html>`);
        return;
      }
      
      console.log('💭 Processing Auth0 callback with code and state');
      
      // Generate the full callback URL for the Auth0 SDK to process
      let fullUrl = `http://localhost:${port}/callback?code=${code}&state=${state}`;
      
      // Add any other parameters that might be present
      const additionalParams = Object.keys(query).filter(key => key !== 'code' && key !== 'state');
      if (additionalParams.length > 0) {
        additionalParams.forEach(key => {
          fullUrl += `&${key}=${encodeURIComponent(query[key])}`;
        });
      }
      
      // Call the callback before responding
      onCallback({
        code,
        state,
        fullUrl,
        urlParts
      });
      
      // Send a success response - UPDATED STYLING, REMOVED SPINNER, ADDED AUTO-CLOSE TIMEOUT
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`<!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Authentication Successful - Denker</title>
          <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
          <style>
            body { 
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
              background-color: #1e1e1e; /* Dark background */
              color: #d4d4d4; /* Light text */
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              margin: 0;
              text-align: center; 
            }
            .container { max-width: 400px; padding: 30px; }
            h1 { color: #4CAF50; margin-bottom: 15px; }
            p { font-size: 16px; line-height: 1.5; }
            .countdown { color: #4CAF50; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <h1>Authentication Complete ✅</h1>
            <p>You have successfully authenticated with Denker!</p>
            <p>This window will close automatically in <span class="countdown" id="countdown">3</span> seconds.</p>
            <p><small>You can also close this window manually if needed.</small></p>
          </div>
          
          <script>
            let seconds = 3;
            const countdownElement = document.getElementById('countdown');
            
            const timer = setInterval(() => {
              seconds--;
              if (countdownElement) {
                countdownElement.textContent = seconds;
              }
              
              if (seconds <= 0) {
                clearInterval(timer);
                try {
                  window.close();
                } catch (e) {
                  console.log('Could not close window automatically:', e);
                }
              }
            }, 1000);
          </script>
        </body>
        </html>`);
    } else if (pathname === '/logout-success') {
      console.log('🔔 Serving logout success page');
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`<!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Logout Successful - Denker</title>
          <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
          <style>
            body { 
              font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
              background-color: #1e1e1e; /* Dark background */
              color: #d4d4d4; /* Light text */
              display: flex;
              justify-content: center;
              align-items: center;
              height: 100vh;
              margin: 0;
              text-align: center; 
            }
            .container { max-width: 400px; padding: 30px; }
            h1 { color: #4CAF50; margin-bottom: 15px; }
            p { font-size: 16px; line-height: 1.5; }
            .countdown { color: #4CAF50; font-weight: bold; }
          </style>
        </head>
        <body>
          <div class="container">
            <h1>Logout Successful ✅</h1>
            <p>You have been successfully logged out from Denker.</p>
            <p>This window will close automatically in <span class="countdown" id="countdown">3</span> seconds.</p>
            <p><small>You can also close this window manually if needed.</small></p>
          </div>
          
          <script>
            let seconds = 3;
            const countdownElement = document.getElementById('countdown');
            
            const timer = setInterval(() => {
              seconds--;
              if (countdownElement) {
                countdownElement.textContent = seconds;
              }
              
              if (seconds <= 0) {
                clearInterval(timer);
                try {
                  window.close();
                } catch (e) {
                  console.log('Could not close window automatically:', e);
                }
              }
            }, 1000);
          </script>
        </body>
        </html>`);
    } else if (urlParts.pathname === '/auth-complete') {
      // Special endpoint that just redirects to the main app
      // This helps escape from any browser window that might be stuck
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Redirecting...</title>
          <script>
            // This is a special helper page that just tries to close itself
            // and ensures the main app window is focused
            try {
              window.close();
            } catch(e) { console.error(e); }
          </script>
        </head>
        <body>
          <p>Authentication complete. This window will close automatically.</p>
        </body>
        </html>
      `);
    } else {
      // Handle other paths with 404
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  });
  
  // Start listening on the specified port
  server.listen(port, '127.0.0.1', () => {
    console.log(`✅ Auth0 callback server running on http://localhost:${port}`);
  });
  
  return server;
}

module.exports = { createAuthServer };

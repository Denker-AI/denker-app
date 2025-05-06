#!/usr/bin/env python3
"""
Diagnostic script to debug the WebSearch MCP server
"""

import asyncio
import json
import subprocess
import sys

async def send_list_tools_request():
    """Send a direct list_tools request to the WebSearch server and print the output."""
    try:
        # Create a list_tools request
        request = {
            "type": "list_tools",
            "id": "debug_request_1"
        }
        
        # Launch the server process
        process = subprocess.Popen(
            ["python", "-m", "mcp_local.servers.websearch.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        print("WebSearch server process started")
        
        # Write the request to stdin
        request_str = json.dumps(request) + "\n"
        print(f"Sending request: {request_str.strip()}")
        process.stdin.write(request_str)
        process.stdin.flush()
        
        # Read the response from stdout with a timeout
        print("Waiting for response...")
        
        # Set up asynchronous reading
        async def read_stdout():
            # Use a loop to read all lines
            count = 0
            while process.poll() is None and count < 10:
                line = process.stdout.readline()
                if line:
                    print(f"Received: {line.strip()}")
                    try:
                        response = json.loads(line)
                        print("Parsed response:")
                        print(f"  Type: {response.get('type')}")
                        print(f"  Tools: {len(response.get('tools', []))}")
                        for i, tool in enumerate(response.get('tools', [])):
                            print(f"  Tool {i+1}: {tool.get('name')} - {tool.get('description')[:50]}...")
                        return True
                    except json.JSONDecodeError:
                        print("Could not parse line as JSON")
                await asyncio.sleep(0.5)
                count += 1
            return False
        
        # Set a timeout
        try:
            success = await asyncio.wait_for(read_stdout(), timeout=10.0)
            if not success:
                print("No valid response received within the timeout period")
        except asyncio.TimeoutError:
            print("Timeout waiting for response")
        
        # Terminate the process
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        
        # Read any stderr output
        stderr_output = process.stderr.read()
        if stderr_output:
            print("\nStderr output:")
            print(stderr_output)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Starting WebSearch server diagnostic...")
    asyncio.run(send_list_tools_request())
    print("Diagnostic complete.") 
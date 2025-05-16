import asyncio
from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent

async def test_websearch():
    # Create MCP app
    app = MCPApp(name='test_app')
    
    async with app.run() as ctx:
        # Create test agent
        agent = Agent(
            name='test_agent',
            server_names=['websearch']
        )
        
        # Initialize agent
        await agent.initialize()
        
        # List tools
        tools_response = await agent.list_tools()
        
        # Print tool names
        if hasattr(tools_response, 'tools'):
            print('Tools available:', [tool.name for tool in tools_response.tools])
        else:
            print('No tools available or unexpected response format:', tools_response)

# Run the test
if __name__ == "__main__":
    asyncio.run(test_websearch()) 
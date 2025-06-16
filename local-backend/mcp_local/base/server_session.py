
class ServerSession:
    """
    Mock implementation of ServerSession for compatibility with mcp_agent.
    """
    
    def __init__(self, name=None, addr=None):
        self.name = name
        self.addr = addr
    
    async def ask(self, *args, **kwargs):
        """Mock implementation"""
        return {"error": "ServerSession is a mock implementation"}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass

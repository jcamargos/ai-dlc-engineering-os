"""Small, dependency-free Python SDK for AI-DLC MCP."""

from .client import AgentShieldClient, AgentShieldError

__all__ = ["AgentShieldClient", "AgentShieldError"]
__version__ = "3.2.0"

"""Small, dependency-free Python SDK for AgentShield MCP."""

from .client import AgentShieldClient, AgentShieldError

__all__ = ["AgentShieldClient", "AgentShieldError"]
__version__ = "3.2.0"

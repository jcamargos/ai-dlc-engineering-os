from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from agentshield_sdk import AgentShieldClient
from agentshield_sdk.client import AgentShieldError


class _Response(io.BytesIO):
    def __init__(self, payload: dict, headers: dict[str, str] | None = None):
        super().__init__(json.dumps(payload).encode())
        self.headers = headers or {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class PythonSdkTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_tool_call_uses_header_and_structured_content(self, open_url):
        open_url.return_value = _Response({"jsonrpc": "2.0", "id": 1, "result": {"structuredContent": {"agent": "security"}}})
        client = AgentShieldClient("https://mcp.example.test/mcp", token="top-secret")
        self.assertEqual(client.route("threat model"), {"agent": "security"})
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer top-secret")
        self.assertNotIn(b"top-secret", request.data)

    def test_endpoint_is_required(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(AgentShieldError):
                AgentShieldClient(token="x")

    @patch.dict("os.environ", {"AI_DLC_CLOUD_URL": "https://mcp.example.test/mcp/"})
    def test_endpoint_from_environment(self):
        self.assertEqual(AgentShieldClient().endpoint, "https://mcp.example.test/mcp")


if __name__ == "__main__":
    unittest.main()

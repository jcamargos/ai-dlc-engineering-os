import assert from "node:assert/strict";
import test from "node:test";
import { AgentShield } from "../dist/index.js";

test("calls MCP tools without leaking token in the body", async () => {
  let captured;
  const client = new AgentShield({ endpoint: "https://mcp.example.test/mcp", token: "secret-token", fetch: async (_url, init) => {
    captured = init;
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { structuredContent: { agent: "security" } } }), { status: 200, headers: { "content-type": "application/json" } });
  }});
  assert.deepEqual(await client.route("threat model"), { agent: "security" });
  assert.equal(JSON.parse(captured.body).params.arguments.task, "threat model");
  assert.equal(captured.body.includes("secret-token"), false);
  assert.equal(captured.headers.authorization, "Bearer secret-token");
});

test("requires an explicit endpoint (no implicit hosted default)", () => {
  const saved = process.env.AI_DLC_CLOUD_URL;
  delete process.env.AI_DLC_CLOUD_URL;
  try { assert.throws(() => new AgentShield({ token: "x" }), /endpoint is required/); }
  finally { if (saved !== undefined) process.env.AI_DLC_CLOUD_URL = saved; }
});

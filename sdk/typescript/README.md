# AgentShield TypeScript SDK

```ts
import { AgentShield } from "@agentshield/sdk";

const shield = new AgentShield({ token: process.env.AGENTSHIELD_TOKEN });
await shield.initialize();
const route = await shield.route("Review this payment migration", "payments");
```

The SDK has no runtime dependencies, supports MCP Streamable HTTP sessions, bounds
requests with a timeout, and never includes the bearer token in serialized errors.

export type JsonObject = Record<string, unknown>;

export interface AgentShieldOptions {
  endpoint?: string;
  token?: string;
  timeoutMs?: number;
  fetch?: typeof globalThis.fetch;
}

export interface SwarmTask {
  id?: string;
  agent: string;
  title: string;
  input?: JsonObject;
  depends_on?: string[];
}

export class AgentShieldError extends Error {
  constructor(message: string, public readonly code?: number) {
    super(message);
    this.name = "AgentShieldError";
  }
}

export class AgentShield {
  readonly endpoint: string;
  readonly timeoutMs: number;
  #token?: string;
  #fetch: typeof globalThis.fetch;
  #requestId = 0;
  #sessionId?: string;

  constructor(options: AgentShieldOptions = {}) {
    const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env;
    const endpoint = (options.endpoint ?? env?.AI_DLC_REMOTE_URL ?? "").trim();
    if (!endpoint) throw new AgentShieldError("endpoint is required: pass { endpoint } or set AI_DLC_REMOTE_URL");
    this.endpoint = endpoint.replace(/\/$/, "");
    this.#token = options.token;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async #rpc<T>(method: string, params: JsonObject = {}): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const headers: Record<string, string> = {
      "content-type": "application/json",
      accept: "application/json, text/event-stream",
      "user-agent": "agentshield-typescript/3.0.2",
    };
    if (this.#token) headers.authorization = `Bearer ${this.#token}`;
    if (this.#sessionId) headers["mcp-session-id"] = this.#sessionId;
    try {
      const response = await this.#fetch(this.endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify({ jsonrpc: "2.0", id: ++this.#requestId, method, params }),
        signal: controller.signal,
      });
      if (!response.ok) throw new AgentShieldError(`AgentShield returned HTTP ${response.status}`, response.status);
      this.#sessionId = response.headers.get("mcp-session-id") ?? this.#sessionId;
      const contentType = response.headers.get("content-type") ?? "";
      let raw = await response.text();
      if (contentType.includes("text/event-stream")) {
        const data = raw.split(/\r?\n/).filter((line) => line.startsWith("data: "));
        raw = data.at(-1)?.slice(6) ?? "{}";
      }
      let envelope: { result?: T; error?: { code?: number; message?: string } };
      try { envelope = JSON.parse(raw) as typeof envelope; }
      catch { throw new AgentShieldError("AgentShield returned an invalid JSON response"); }
      if (envelope.error) throw new AgentShieldError(`MCP ${envelope.error.code ?? "error"}: ${envelope.error.message ?? "request failed"}`, envelope.error.code);
      return envelope.result as T;
    } finally {
      clearTimeout(timer);
    }
  }

  initialize(): Promise<JsonObject> {
    return this.#rpc("initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "agentshield-typescript", version: "3.0.2" } });
  }

  async tools(): Promise<JsonObject[]> {
    const result = await this.#rpc<{ tools: JsonObject[] }>("tools/list");
    return result.tools;
  }

  async call<T = unknown>(name: string, args: JsonObject = {}): Promise<T> {
    const result = await this.#rpc<{ isError?: boolean; structuredContent?: T; content?: Array<{ type: string; text?: string }> }>("tools/call", { name, arguments: args });
    if (result.isError) throw new AgentShieldError(result.content?.map((item) => item.text ?? "").join(" ") || `${name} failed`);
    if (result.structuredContent !== undefined) return result.structuredContent;
    const text = result.content?.length === 1 ? result.content[0]?.text : undefined;
    if (text !== undefined) {
      try { return JSON.parse(text) as T; } catch { return text as T; }
    }
    return result.content as T;
  }

  route(task: string, projectId?: string): Promise<unknown> {
    return this.call("route_task", { task, ...(projectId ? { project_id: projectId } : {}) });
  }

  remember(input: { kind: string; title: string; content: string; projectId?: string; tags?: string[] }): Promise<unknown> {
    return this.call("save_memory", { kind: input.kind, title: input.title, content: input.content, project_id: input.projectId ?? "", tags: (input.tags ?? []).join(",") });
  }

  search(query: string, projectId?: string, limit = 8): Promise<unknown> {
    return this.call("search_memory", { query, project_id: projectId ?? "", limit });
  }

  createSwarm(projectId: string, objective: string, tasks: SwarmTask[], maxParallel = 4): Promise<unknown> {
    return this.call("create_swarm", { project_id: projectId, objective, tasks, max_parallel: maxParallel });
  }
}

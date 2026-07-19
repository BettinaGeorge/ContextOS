// Typed REST client for the ContextOS backend, matching
// specs/001-trace-doc-to-code/contracts/api.md exactly. Grows as each
// endpoint is implemented (Phase 3+).

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly error: string,
    public readonly detail: string | null,
  ) {
    super(`${error}${detail ? `: ${detail}` : ""}`);
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, headers, ...rest } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ error: "unknown_error", detail: null }));
    throw new ApiError(response.status, body.error ?? "unknown_error", body.detail ?? null);
  }
  return response.json() as Promise<T>;
}

// --- GET /me ---
export interface MeResponse {
  user_id: string;
  workspace_id: string | null;
}

export function getMe(token: string): Promise<MeResponse> {
  return request<MeResponse>("/me", { token });
}

// --- POST /workspaces ---
export interface Workspace {
  id: string;
  name: string;
  created_at: string;
}

export function createWorkspace(token: string, name: string): Promise<Workspace> {
  return request<Workspace>("/workspaces", {
    method: "POST",
    token,
    body: JSON.stringify({ name }),
  });
}

// --- POST /connectors/github, POST /connectors/notion ---
export interface ConnectorCreatedResponse {
  connector_id: string;
  status: string;
}

export function connectGithub(
  token: string,
  repo: string,
  authCodeOrToken: string,
): Promise<ConnectorCreatedResponse> {
  return request<ConnectorCreatedResponse>("/connectors/github", {
    method: "POST",
    token,
    body: JSON.stringify({ repo, auth_code_or_token: authCodeOrToken }),
  });
}

export function connectNotion(
  token: string,
  integrationToken: string,
  pageIds: string[],
): Promise<ConnectorCreatedResponse> {
  return request<ConnectorCreatedResponse>("/connectors/notion", {
    method: "POST",
    token,
    body: JSON.stringify({ integration_token: integrationToken, page_ids: pageIds }),
  });
}

// --- GET /connectors/{id}/status ---
export interface ConnectorStatusResponse {
  connector_id: string;
  source_system: "github" | "notion";
  status: "connected" | "ingesting" | "complete" | "failed" | "needs_reconnect";
  last_ingested_at: string | null;
  error_message: string | null;
}

export function getConnectorStatus(
  token: string,
  connectorId: string,
): Promise<ConnectorStatusResponse> {
  return request<ConnectorStatusResponse>(`/connectors/${connectorId}/status`, { token });
}

// --- POST /ingest/{connector_id}, GET /ingest/{job_id}/status ---
export interface IngestJobResponse {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  error_message?: string | null;
}

export function triggerIngest(token: string, connectorId: string): Promise<IngestJobResponse> {
  return request<IngestJobResponse>(`/ingest/${connectorId}`, { method: "POST", token });
}

export function getIngestStatus(token: string, jobId: string): Promise<IngestJobResponse> {
  return request<IngestJobResponse>(`/ingest/${jobId}/status`, { token });
}

// --- POST /ask ---
export type CitationOrigin = "explicit" | "metadata-derived" | "inferred";

export interface Citation {
  artifact_id: string;
  source_url: string;
  artifact_type: "source_file" | "commit" | "pull_request" | "issue" | "document";
  origin: CitationOrigin;
}

export interface AskResponse {
  answer: string;
  abstained: boolean;
  citations: Citation[];
}

export function askQuestion(
  token: string,
  question: string,
  notionDocUrl?: string,
): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    token,
    body: JSON.stringify({ question, notion_doc_url: notionDocUrl ?? null }),
  });
}

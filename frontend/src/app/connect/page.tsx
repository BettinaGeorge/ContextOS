"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/useSession";
import { ApiError, connectGithub, connectNotion, triggerIngest } from "@/lib/api";

type ConnectorState = { connectorId: string | null; status: string | null; error: string | null };

export default function ConnectPage() {
  const { token, loading } = useSession();

  const [repo, setRepo] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [github, setGithub] = useState<ConnectorState>({
    connectorId: null,
    status: null,
    error: null,
  });

  const [notionToken, setNotionToken] = useState("");
  const [pageIds, setPageIds] = useState("");
  const [notion, setNotion] = useState<ConnectorState>({
    connectorId: null,
    status: null,
    error: null,
  });

  async function handleConnectGithub(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    try {
      const result = await connectGithub(token, repo, githubToken);
      setGithub({ connectorId: result.connector_id, status: result.status, error: null });
    } catch (err) {
      setGithub((s) => ({ ...s, error: err instanceof ApiError ? err.message : "Failed to connect" }));
    }
  }

  async function handleConnectNotion(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    try {
      const ids = pageIds.split(",").map((id) => id.trim()).filter(Boolean);
      const result = await connectNotion(token, notionToken, ids);
      setNotion({ connectorId: result.connector_id, status: result.status, error: null });
    } catch (err) {
      setNotion((s) => ({ ...s, error: err instanceof ApiError ? err.message : "Failed to connect" }));
    }
  }

  async function handleTriggerIngest(
    connectorState: ConnectorState,
    setState: (s: ConnectorState) => void,
  ) {
    if (!token || !connectorState.connectorId) return;
    try {
      const job = await triggerIngest(token, connectorState.connectorId);
      setState({ ...connectorState, status: `ingest ${job.status}`, error: null });
    } catch (err) {
      setState({
        ...connectorState,
        error: err instanceof ApiError ? err.message : "Failed to trigger ingestion",
      });
    }
  }

  if (loading) {
    return <PageShell><p className="text-sm text-zinc-500">Loading...</p></PageShell>;
  }

  return (
    <PageShell>
      <div className="flex w-full max-w-md flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Connect GitHub</CardTitle>
            <CardDescription>One repository per workspace (PRD §4).</CardDescription>
          </CardHeader>
          <CardContent>
            {!github.connectorId ? (
              <form onSubmit={handleConnectGithub} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="repo">Repository (owner/name)</Label>
                  <Input
                    id="repo"
                    required
                    value={repo}
                    onChange={(e) => setRepo(e.target.value)}
                    placeholder="acme/widgets"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="gh-token">Personal access token</Label>
                  <Input
                    id="gh-token"
                    type="password"
                    required
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                  />
                </div>
                <Button type="submit">Connect</Button>
                {github.error && <p className="text-sm text-red-600">{github.error}</p>}
              </form>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-zinc-600">Status: {github.status}</p>
                <Button variant="outline" onClick={() => handleTriggerIngest(github, setGithub)}>
                  Start ingestion
                </Button>
                {github.error && <p className="text-sm text-red-600">{github.error}</p>}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Connect Notion</CardTitle>
            <CardDescription>Selected pages only, comma-separated page IDs.</CardDescription>
          </CardHeader>
          <CardContent>
            {!notion.connectorId ? (
              <form onSubmit={handleConnectNotion} className="flex flex-col gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="notion-token">Integration token</Label>
                  <Input
                    id="notion-token"
                    type="password"
                    required
                    value={notionToken}
                    onChange={(e) => setNotionToken(e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="page-ids">Page IDs</Label>
                  <Input
                    id="page-ids"
                    required
                    value={pageIds}
                    onChange={(e) => setPageIds(e.target.value)}
                    placeholder="page-id-1, page-id-2"
                  />
                </div>
                <Button type="submit">Connect</Button>
                {notion.error && <p className="text-sm text-red-600">{notion.error}</p>}
              </form>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-sm text-zinc-600">Status: {notion.status}</p>
                <Button variant="outline" onClick={() => handleTriggerIngest(notion, setNotion)}>
                  Start ingestion
                </Button>
                {notion.error && <p className="text-sm text-red-600">{notion.error}</p>}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-zinc-50 p-8 dark:bg-black">
      {children}
    </div>
  );
}

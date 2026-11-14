"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useSession } from "@/lib/useSession";
import { ApiError, listConnectors, type ConnectorStatusResponse } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
const TERMINAL_STATUSES = new Set(["complete", "failed", "needs_reconnect"]);

const STATUS_LABEL: Record<ConnectorStatusResponse["status"], string> = {
  connected: "Connected, not yet ingested",
  ingesting: "Ingesting...",
  complete: "Complete",
  failed: "Failed",
  needs_reconnect: "Needs reconnect",
};

const STATUS_BADGE_CLASS: Record<ConnectorStatusResponse["status"], string> = {
  connected: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  ingesting: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  complete: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  needs_reconnect: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
};

export default function StatusPage() {
  const { token, loading } = useSession();
  const [connectors, setConnectors] = useState<ConnectorStatusResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!token) return;

    async function fetchOnce() {
      try {
        const result = await listConnectors(token!);
        setConnectors(result);
        setError(null);
        const allTerminalOrEmpty =
          result.length === 0 || result.every((c) => TERMINAL_STATUSES.has(c.status));
        if (allTerminalOrEmpty && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load connector status");
      }
    }

    fetchOnce();
    pollRef.current = setInterval(fetchOnce, POLL_INTERVAL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [token]);

  if (loading) {
    return <PageShell><p className="text-sm text-zinc-500">Loading...</p></PageShell>;
  }

  return (
    <PageShell>
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Ingestion Status</CardTitle>
          <CardDescription>
            Updates automatically every {POLL_INTERVAL_MS / 1000}s while ingestion is running.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {error && <p className="text-sm text-red-600">{error}</p>}

          {connectors === null && !error && (
            <p className="text-sm text-zinc-500">Loading connector status...</p>
          )}

          {connectors !== null && connectors.length === 0 && (
            <p className="text-sm text-zinc-500">
              No connectors yet — connect GitHub or Notion first.
            </p>
          )}

          {connectors?.map((c) => {
            // An error on an ingesting connector means an earlier attempt failed and a
            // retry is coming; on the very first attempt there is no error yet.
            const retrying =
              c.status === "ingesting" && (c.ingestion_attempts ?? 0) > 0 && !!c.error_message;
            return (
            <div
              key={c.connector_id}
              className="flex flex-col gap-1 rounded-md border border-zinc-200 p-3 dark:border-zinc-800"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize">{c.source_system}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE_CLASS[c.status]}`}
                >
                  {STATUS_LABEL[c.status]}
                </span>
              </div>
              {c.last_ingested_at && (
                <span className="text-xs text-zinc-500">
                  Last ingested: {new Date(c.last_ingested_at).toLocaleString()}
                </span>
              )}
              {retrying && (
                <span className="text-xs text-zinc-500">
                  Retrying (attempt {c.ingestion_attempts} of {c.max_attempts})
                </span>
              )}
              {c.status === "failed" && c.ingestion_attempts != null && c.max_attempts != null && (
                <span className="text-xs text-red-600">
                  Failed after {c.ingestion_attempts} of {c.max_attempts} attempts
                </span>
              )}
              {c.error_message && (
                <span className={`text-xs ${retrying ? "text-zinc-500" : "text-red-600"}`}>
                  {c.error_message}
                </span>
              )}
            </div>
            );
          })}
        </CardContent>
      </Card>
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

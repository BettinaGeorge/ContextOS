import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StatusPage from "@/app/status/page";
import * as api from "@/lib/api";
import * as sessionHook from "@/lib/useSession";

vi.mock("@/lib/useSession");
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return { ...actual, listConnectors: vi.fn() };
});

function connector(overrides: Partial<api.ConnectorStatusResponse>): api.ConnectorStatusResponse {
  return {
    connector_id: "c1",
    source_system: "github",
    status: "ingesting",
    last_ingested_at: null,
    error_message: null,
    ingestion_attempts: null,
    max_attempts: null,
    next_attempt_at: null,
    ...overrides,
  };
}

async function renderWith(connectors: api.ConnectorStatusResponse[]) {
  vi.mocked(sessionHook.useSession).mockReturnValue({
    session: { access_token: "fake-token" } as never,
    loading: false,
    token: "fake-token",
    signInWithEmail: vi.fn(),
    signOut: vi.fn(),
  });
  vi.mocked(api.listConnectors).mockResolvedValue(connectors);
  render(<StatusPage />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

describe("StatusPage retries", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("shows the retry count and a muted error while retries remain", async () => {
    await renderWith([
      connector({
        ingestion_attempts: 2,
        max_attempts: 3,
        error_message: "GitHub API is down",
        next_attempt_at: "2026-11-14T10:00:30Z",
      }),
    ]);

    expect(screen.getByText("Retrying (attempt 2 of 3)")).toBeTruthy();
    const error = screen.getByText("GitHub API is down");
    expect(error.className).toContain("text-zinc-500");
    expect(error.className).not.toContain("text-red-600");
  });

  it("does not claim a retry during the very first attempt", async () => {
    await renderWith([connector({ ingestion_attempts: 1, max_attempts: 3 })]);

    expect(screen.queryByText(/Retrying/)).toBeNull();
  });

  it("shows the attempt count and the error in the failure style once it has failed", async () => {
    await renderWith([
      connector({
        status: "failed",
        ingestion_attempts: 3,
        max_attempts: 3,
        error_message: "GitHub API is down",
      }),
    ]);

    expect(screen.getByText("Failed after 3 of 3 attempts")).toBeTruthy();
    const error = screen.getByText("GitHub API is down");
    expect(error.className).toContain("text-red-600");
    expect(screen.queryByText(/Retrying/)).toBeNull();
  });

  it("keeps polling while a retry is pending", async () => {
    await renderWith([
      connector({ ingestion_attempts: 1, max_attempts: 3, error_message: "temporary outage" }),
    ]);
    expect(api.listConnectors).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(api.listConnectors).toHaveBeenCalledTimes(2);
  });
});

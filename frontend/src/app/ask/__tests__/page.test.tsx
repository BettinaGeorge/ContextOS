import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AskPage from "@/app/ask/page";
import * as api from "@/lib/api";
import * as sessionHook from "@/lib/useSession";

vi.mock("@/lib/useSession");
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return { ...actual, askQuestion: vi.fn() };
});

function mockSession() {
  vi.mocked(sessionHook.useSession).mockReturnValue({
    session: { access_token: "fake-token" } as never,
    loading: false,
    token: "fake-token",
    signInWithEmail: vi.fn(),
    signOut: vi.fn(),
  });
}

describe("AskPage", () => {
  it("labels an explicit citation differently from an inferred one", async () => {
    mockSession();
    vi.mocked(api.askQuestion).mockResolvedValue({
      answer: "The spinner is implemented here.",
      abstained: false,
      citations: [
        {
          artifact_id: "1",
          source_url: "https://github.com/acme/widgets/pull/1",
          artifact_type: "pull_request",
          origin: "explicit",
        },
        {
          artifact_id: "2",
          source_url: "https://github.com/acme/widgets/blob/HEAD/spinner.py",
          artifact_type: "source_file",
          origin: "inferred",
        },
      ],
    });

    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "What implements the spinner?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() => expect(screen.getByText("Explicit link")).toBeInTheDocument());
    expect(screen.getByText("Inferred (semantic match)")).toBeInTheDocument();
  });

  it("renders the abstained state without a citations section", async () => {
    mockSession();
    vi.mocked(api.askQuestion).mockResolvedValue({
      answer: "No relevant evidence was found.",
      abstained: true,
      citations: [],
    });

    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "unrelated question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await waitFor(() =>
      expect(screen.getByText("No confident answer")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Citations")).not.toBeInTheDocument();
  });
});

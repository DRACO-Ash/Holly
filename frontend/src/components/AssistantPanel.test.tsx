// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getEvaluation, runEvaluation } from "../api/assistant";
import { anEvaluation } from "../test/fixtures";
import type { AssistantEvaluation, StructuredEvaluation } from "../types";
import AssistantPanel from "./AssistantPanel";

vi.mock("../api/assistant");

function structured(overrides: Partial<StructuredEvaluation> = {}): StructuredEvaluation {
  return {
    summary: "Synthetic structured summary",
    applicable_procedures: [],
    next_actions: [],
    open_questions: [],
    ...overrides,
  };
}

function pending<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

// The panel once its evaluation has loaded.
async function panelFor(id = "n-1") {
  const view = render(<AssistantPanel notificationId={id} />);
  await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
  return view;
}

beforeEach(() => {
  vi.mocked(getEvaluation).mockReset().mockResolvedValue(null);
  vi.mocked(runEvaluation).mockReset().mockResolvedValue(anEvaluation());
});

describe("the assistant panel", () => {
  it("says it is loading, then offers to run the assistant on a notice not yet analysed", async () => {
    const answer = pending<AssistantEvaluation | null>();
    vi.mocked(getEvaluation).mockReturnValue(answer.promise);
    render(<AssistantPanel notificationId="n-1" />);
    expect(screen.getByText("Loading...")).toBeTruthy();
    expect(getEvaluation).toHaveBeenCalledWith("n-1");
    await act(async () => answer.resolve(null));
    expect(screen.getByText(/Not yet analysed/)).toBeTruthy();
  });

  it("runs the assistant, saying so meanwhile, and shows what it found", async () => {
    await panelFor();
    const run = pending<AssistantEvaluation>();
    vi.mocked(runEvaluation).mockReturnValue(run.promise);
    fireEvent.click(screen.getByRole("button", { name: "Run assistant" }));
    expect(runEvaluation).toHaveBeenCalledWith("n-1");
    const busy = (await screen.findByRole("button", { name: "Analysing..." })) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    await act(async () => run.resolve(anEvaluation()));
    expect(screen.getByText("Synthetic structured summary")).toBeTruthy();
    expect(screen.getByText("No actions recommended. Informational only.")).toBeTruthy();
  });

  it("shows why the assistant could not run", async () => {
    vi.mocked(runEvaluation).mockRejectedValue({ response: { data: { detail: "Assistant off" } } });
    await panelFor();
    fireEvent.click(screen.getByRole("button", { name: "Run assistant" }));
    expect(await screen.findByText("Assistant off")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run assistant" })).toBeTruthy();
  });

  it("says the evaluation could not load when the failure gives no reason", async () => {
    vi.mocked(getEvaluation).mockRejectedValue("unexpected");
    await panelFor();
    expect(screen.getByText("Failed to load assistant evaluation.")).toBeTruthy();
  });

  it("lists the next actions with their urgency and deadline, the procedures and the questions", async () => {
    vi.mocked(getEvaluation).mockResolvedValue(
      anEvaluation({
        model: "test-model",
        evaluated_at: "2026-01-02T05:06:07Z",
        structured: structured({
          next_actions: [
            {
              action: "Act now",
              urgency: "high",
              deadline: "2026-01-02T06:00:00Z",
              rationale: "Why now",
            },
            { action: "Act soon", urgency: "medium", deadline: null, rationale: "Why soon" },
            { action: "Act later", urgency: "low", deadline: null, rationale: "Why later" },
            { action: "Act maybe", urgency: "unclear", deadline: null, rationale: "Why maybe" },
          ],
          applicable_procedures: [
            { procedure_id: "p-1", name: "Synthetic procedure", reason: "Fits" },
          ],
          open_questions: ["Synthetic question?"],
        }),
      }),
    );
    await panelFor();
    expect(screen.getByText("test-model · 2026-01-02 05:06:07")).toBeTruthy();
    const actions = screen
      .getAllByRole("listitem")
      .filter((li) => li.querySelector(".action-head"));
    expect(actions.map((li) => li.querySelector(".urgency-pill")?.className)).toEqual([
      "urgency-pill urgency-high",
      "urgency-pill urgency-medium",
      "urgency-pill urgency-low",
      "urgency-pill",
    ]);
    expect(within(actions[0]).getByText("By 2026-01-02 06:00:00")).toBeTruthy();
    expect(within(actions[0]).getByText("Why now")).toBeTruthy();
    expect(actions[1].querySelector(".action-deadline")).toBeNull();
    expect(screen.getByText("Synthetic procedure")).toBeTruthy();
    expect(screen.getByText("Fits")).toBeTruthy();
    expect(screen.getByText("Synthetic question?")).toBeTruthy();
  });

  it("falls back to the plain summary, says when the structure failed, and copes with what is missing", async () => {
    vi.mocked(getEvaluation).mockResolvedValue(
      anEvaluation({
        summary: "Synthetic plain summary",
        evaluated_at: "",
        error: "unparseable output",
        structured: { summary: "" } as StructuredEvaluation,
      }),
    );
    await panelFor();
    expect(screen.getByText("Synthetic plain summary")).toBeTruthy();
    expect(screen.getByText("test-model · n/a")).toBeTruthy();
    expect(
      screen.getByText("Assistant could not produce a structured evaluation: unparseable output"),
    ).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Applicable procedures" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Open questions" })).toBeNull();
  });

  it("re-evaluates on request, saying so meanwhile, and shows why it failed", async () => {
    vi.mocked(getEvaluation).mockResolvedValue(anEvaluation());
    await panelFor();
    const run = pending<AssistantEvaluation>();
    vi.mocked(runEvaluation).mockReturnValue(run.promise);
    fireEvent.click(screen.getByRole("button", { name: "Re-evaluate" }));
    expect(await screen.findByRole("button", { name: "Re-analysing..." })).toBeTruthy();
    await act(async () => run.reject({ response: { data: { detail: "Try later" } } }));
    expect(screen.getByText("Try later")).toBeTruthy();
    vi.mocked(runEvaluation).mockRejectedValueOnce("unexpected");
    fireEvent.click(screen.getByRole("button", { name: "Re-evaluate" }));
    expect(await screen.findByText("Failed to run assistant evaluation.")).toBeTruthy();
  });

  it("loads again for another notice", async () => {
    const view = await panelFor("n-1");
    view.rerender(<AssistantPanel notificationId="n-2" />);
    await waitFor(() => expect(getEvaluation).toHaveBeenLastCalledWith("n-2"));
    await waitFor(() => expect(screen.queryByText("Loading...")).toBeNull());
  });

  it("shows the notice it is on, never a late answer about the notice before", async () => {
    const late = pending<AssistantEvaluation | null>();
    vi.mocked(getEvaluation)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValueOnce(anEvaluation({ structured: structured({ summary: "About n-2" }) }));
    const view = render(<AssistantPanel notificationId="n-1" />);
    view.rerender(<AssistantPanel notificationId="n-2" />);
    expect(await screen.findByText("About n-2")).toBeTruthy();
    await act(async () =>
      late.resolve(anEvaluation({ structured: structured({ summary: "About n-1" }) })),
    );
    expect(screen.getByText("About n-2")).toBeTruthy();
    expect(screen.queryByText("About n-1")).toBeNull();
  });

  it("keeps loading the notice it is on when the notice before answers first", async () => {
    const late = pending<AssistantEvaluation | null>();
    const current = pending<AssistantEvaluation | null>();
    vi.mocked(getEvaluation).mockReturnValueOnce(late.promise).mockReturnValueOnce(current.promise);
    const view = render(<AssistantPanel notificationId="n-1" />);
    view.rerender(<AssistantPanel notificationId="n-2" />);
    await act(async () => late.resolve(null));
    expect(screen.getByText("Loading...")).toBeTruthy();
    await act(async () =>
      current.resolve(anEvaluation({ structured: structured({ summary: "About n-2" }) })),
    );
    expect(screen.getByText("About n-2")).toBeTruthy();
  });

  it("never shows why the assistant failed on the notice before", async () => {
    const late = pending<AssistantEvaluation | null>();
    vi.mocked(getEvaluation).mockReturnValueOnce(late.promise).mockResolvedValueOnce(null);
    const view = render(<AssistantPanel notificationId="n-1" />);
    view.rerender(<AssistantPanel notificationId="n-2" />);
    expect(await screen.findByText(/Not yet analysed/)).toBeTruthy();
    await act(async () => late.reject({ response: { data: { detail: "Old failure" } } }));
    expect(screen.queryByText("Old failure")).toBeNull();
  });
});

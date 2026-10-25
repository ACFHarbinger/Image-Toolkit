import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { HieEditorView } from "./HieEditorView";

describe("HieEditorView", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders editor header, viewport, and RL assistance tools", () => {
    render(<HieEditorView />);

    expect(screen.getByText("Hybrid Image Editor")).toBeInTheDocument();
    expect(screen.getByText("NON-DESTRUCTIVE")).toBeInTheDocument();
    expect(screen.getByText("AI / RL Assistance")).toBeInTheDocument();
    expect(screen.getByText("Brush Assistant")).toBeInTheDocument();
    expect(screen.getByText("Tone Agent")).toBeInTheDocument();
    expect(screen.getByText("Composition Optimizer")).toBeInTheDocument();
  });

  test("generates and accepts assistance proposal", async () => {
    const showModal = vi.fn();
    render(<HieEditorView showModal={showModal} />);

    const previewBtn = screen.getByRole("button", { name: /Preview Assistance/i });
    fireEvent.click(previewBtn);

    expect(await screen.findByText("Proposal Ready")).toBeInTheDocument();
    expect(screen.getByText("Inspectable action proposal calculated by HIE middleware.")).toBeInTheDocument();

    const acceptBtn = await screen.findByRole("button", { name: /Accept into History/i });
    fireEvent.click(acceptBtn);

    await waitFor(() => {
      expect(showModal).toHaveBeenCalledWith("Proposal accepted and merged into node stack", "success", 2000);
    });
  });

  test("opens media and exports document", async () => {
    const showModal = vi.fn();
    render(<HieEditorView showModal={showModal} />);

    const openBtn = screen.getByRole("button", { name: /Open Media/i });
    fireEvent.click(openBtn);

    await waitFor(() => {
      expect(showModal).toHaveBeenCalledWith("Select image or video sequence for Hybrid Image Editor...", "info", 2000);
    });

    const exportBtn = screen.getByRole("button", { name: /Export/i });
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(showModal).toHaveBeenCalledWith("Exporting document via HIE render pipeline...", "info", 2500);
    });
  });
});

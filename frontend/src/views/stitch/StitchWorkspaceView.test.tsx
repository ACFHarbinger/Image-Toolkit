import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { StitchWorkspaceView } from "./StitchWorkspaceView";

describe("StitchWorkspaceView", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders ASP workspace header, 8 panel buttons, and viewport", () => {
    render(<StitchWorkspaceView />);

    expect(screen.getByText("Anime Stitch Pipeline (ASP)")).toBeInTheDocument();
    expect(screen.getByText("WAVE 8 / E-01")).toBeInTheDocument();
    expect(screen.getByText("Stitch Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Match Graph")).toBeInTheDocument();
    expect(screen.getByText("Adjustments")).toBeInTheDocument();
    expect(screen.getByText("Canvas Layout")).toBeInTheDocument();
    expect(screen.getByText("Statistics")).toBeInTheDocument();
    expect(screen.getByText("Sequence Builder")).toBeInTheDocument();
    expect(screen.getByText("Hybrid HITL")).toBeInTheDocument();
    expect(screen.getByText("Animation Clusters")).toBeInTheDocument();
  });

  test("switches between panels", () => {
    render(<StitchWorkspaceView />);

    const graphBtn = screen.getByRole("button", { name: /Match Graph/i });
    fireEvent.click(graphBtn);

    expect(screen.getByText(/ASP Composite Viewport \(Match Graph\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Route: stitch\.graph/i)).toBeInTheDocument();
  });

  test("validates required input directory before running stitch", () => {
    const showModal = vi.fn();
    render(<StitchWorkspaceView showModal={showModal} />);

    const runBtn = screen.getByRole("button", { name: /Run Stitch/i });
    fireEvent.click(runBtn);

    expect(showModal).toHaveBeenCalledWith("Please specify an input frame sequence directory", "error");
    expect(screen.getByText("Error: Missing frame input path")).toBeInTheDocument();
  });

  test("initiates stitch job when input is provided", () => {
    const showModal = vi.fn();
    render(<StitchWorkspaceView showModal={showModal} />);

    const dirInput = screen.getByPlaceholderText("/path/to/frames");
    fireEvent.change(dirInput, { target: { value: "/data/anime_shot_01" } });

    const runBtn = screen.getByRole("button", { name: /Run Stitch/i });
    fireEvent.click(runBtn);

    expect(showModal).toHaveBeenCalledWith("Stitching sequence with anime-pan preset...", "info", 2000);
    expect(screen.getByText("Running alignment & stitching pipeline...")).toBeInTheDocument();
  });
});

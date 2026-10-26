import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { MangaWorkspaceView } from "./MangaWorkspaceView";
import { MangaColorizationView } from "./MangaColorizationView";
import { MangaAnimationView } from "./MangaAnimationView";
import { MangaPuppeteeringView } from "./MangaPuppeteeringView";

describe("MangaWorkspaceView", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders CSG workspace header and 3 mode buttons", () => {
    render(<MangaWorkspaceView />);

    expect(screen.getByText("Cel-Shaded Generator (CSG)")).toBeInTheDocument();
    expect(screen.getByText("WAVE 8 / E-03")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Colorization" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Animation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Puppeteering" })).toBeInTheDocument();
  });

  test("switches between colorization, animation, and puppeteering modes", () => {
    render(<MangaWorkspaceView />);

    const animBtn = screen.getByRole("button", { name: "Animation" });
    fireEvent.click(animBtn);

    expect(screen.getByText(/CSG Canvas Viewport — Animation/i)).toBeInTheDocument();
    expect(screen.getByText(/Screentone Guard:/i)).toBeInTheDocument();
    expect(screen.getByText(/FFT BANDPASS/i)).toBeInTheDocument();

    const puppetBtn = screen.getByRole("button", { name: "Puppeteering" });
    fireEvent.click(puppetBtn);

    expect(screen.getByText(/CSG Canvas Viewport — Puppeteering/i)).toBeInTheDocument();
    expect(screen.getByText(/ARAP Rig:/i)).toBeInTheDocument();
  });

  test("validates source manga before solving", () => {
    const showModal = vi.fn();
    render(<MangaWorkspaceView showModal={showModal} />);

    const execBtn = screen.getByRole("button", { name: /Execute colorization/i });
    fireEvent.click(execBtn);

    expect(showModal).toHaveBeenCalledWith("Please select a line-art or manga plate", "error");
    expect(screen.getByText("Error: Missing source manga image")).toBeInTheDocument();
  });

  test("sub-views render with correct initial mode", () => {
    const { unmount: u1 } = render(<MangaColorizationView />);
    expect(screen.getByText(/Mode: manga\.colorization/i)).toBeInTheDocument();
    u1();

    const { unmount: u2 } = render(<MangaAnimationView />);
    expect(screen.getByText(/Mode: manga\.animation/i)).toBeInTheDocument();
    u2();

    render(<MangaPuppeteeringView />);
    expect(screen.getByText(/Mode: manga\.puppeteering/i)).toBeInTheDocument();
  });
});

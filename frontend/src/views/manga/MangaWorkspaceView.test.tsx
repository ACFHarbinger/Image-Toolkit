import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { HostClient } from "../../hostclient";
import { MangaWorkspaceView } from "./MangaWorkspaceView";
import { MangaColorizationView } from "./MangaColorizationView";
import { MangaAnimationView } from "./MangaAnimationView";
import { MangaPuppeteeringView } from "./MangaPuppeteeringView";

type MangaHostClientMock = ReturnType<typeof makeHostClient>;

function makeHostClient() {
  return {
    csgColorizeScribble: vi.fn(),
    csgColorizeReference: vi.fn(),
    csgArapDeform: vi.fn(),
    csgPropagateSequence: vi.fn(),
  };
}

/** The view takes the real HostClient; the mock only implements the csg methods. */
const asHostClient = (mock: MangaHostClientMock) => mock as unknown as HostClient;

describe("MangaWorkspaceView", () => {
  afterEach(() => {
    cleanup();
  });
  beforeEach(() => {
    vi.restoreAllMocks();
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

  test("without a host client, execute reports the missing client", () => {
    const showModal = vi.fn();
    render(<MangaWorkspaceView showModal={showModal} />);

    fireEvent.click(screen.getByRole("button", { name: /Execute colorization/i }));

    expect(showModal).toHaveBeenCalledWith("Host client unavailable", "error");
    expect(screen.getByText("Error: Host client unavailable")).toBeInTheDocument();
  });

  test("validates source manga before solving", () => {
    const showModal = vi.fn();
    render(<MangaWorkspaceView showModal={showModal} hostClient={asHostClient(makeHostClient())} />);

    fireEvent.click(screen.getByRole("button", { name: /Execute colorization/i }));

    expect(showModal).toHaveBeenCalledWith("Please select a line-art or manga plate", "error");
    expect(screen.getByText("Error: Missing source manga image")).toBeInTheDocument();
  });

  test("colorization with a reference calls csgColorizeReference", async () => {
    const hostClient = makeHostClient();
    hostClient.csgColorizeReference.mockResolvedValue({
      success: true,
      output_path: "/tmp/out.png",
      width: 100,
      height: 100,
      elapsed_seconds: 0.1,
    });
    const showModal = vi.fn();
    render(
      <MangaWorkspaceView
        showModal={showModal}
        hostClient={asHostClient(hostClient)}
      />
    );

    fireEvent.change(screen.getByPlaceholderText("/path/to/lineart.png"), {
      target: { value: "/lineart.png" },
    });
    fireEvent.change(screen.getByPlaceholderText("/path/to/reference_palette.png"), {
      target: { value: "/palette.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Execute colorization/i }));

    await vi.waitFor(() => {
      expect(screen.getByText("Colorization complete: /tmp/out.png")).toBeInTheDocument();
    });
    expect(hostClient.csgColorizeReference).toHaveBeenCalledWith({
      lineart_path: "/lineart.png",
      reference_path: "/palette.png",
    });
    expect(hostClient.csgColorizeScribble).not.toHaveBeenCalled();
    expect(showModal).toHaveBeenCalledWith("Colorization generated successfully", "success", 2000);
  });

  test("colorization with only scribble hints calls csgColorizeScribble", async () => {
    const hostClient = makeHostClient();
    hostClient.csgColorizeScribble.mockResolvedValue({
      success: true,
      output_path: "/tmp/scribble.png",
      width: 100,
      height: 100,
      elapsed_seconds: 0.1,
    });
    render(<MangaWorkspaceView hostClient={asHostClient(hostClient)} />);

    fireEvent.change(screen.getByPlaceholderText("/path/to/lineart.png"), {
      target: { value: "/lineart.png" },
    });
    fireEvent.change(screen.getByPlaceholderText("/path/to/scribble_hints.png"), {
      target: { value: "/hints.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Execute colorization/i }));

    await vi.waitFor(() => {
      expect(screen.getByText("Colorization complete: /tmp/scribble.png")).toBeInTheDocument();
    });
    expect(hostClient.csgColorizeScribble).toHaveBeenCalledWith({
      lineart_path: "/lineart.png",
      scribble_path: "/hints.png",
    });
  });

  test("animation propagates the frame sequence", async () => {
    const hostClient = makeHostClient();
    hostClient.csgPropagateSequence.mockResolvedValue({
      success: true,
      output_paths: ["/o/1.png"],
      frames_processed: 2,
      elapsed_seconds: 0.2,
    });
    render(<MangaWorkspaceView hostClient={asHostClient(hostClient)} />);

    fireEvent.click(screen.getByRole("button", { name: "Animation" }));
    fireEvent.change(screen.getByPlaceholderText(/frame_001/), {
      target: { value: "/f1.png\n/f2.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Execute animation/i }));

    await vi.waitFor(() => {
      expect(screen.getByText("Propagated 2 frame(s)")).toBeInTheDocument();
    });
    expect(hostClient.csgPropagateSequence).toHaveBeenCalledWith({
      frame_paths: ["/f1.png", "/f2.png"],
    });
  });

  test("puppeteering deforms via ARAP and reports the mesh vertex count", async () => {
    const hostClient = makeHostClient();
    hostClient.csgArapDeform.mockResolvedValue({
      success: true,
      output_path: "/tmp/pose.png",
      num_vertices: 57,
      num_triangles: 90,
      elapsed_seconds: 0.3,
    });
    render(<MangaWorkspaceView hostClient={asHostClient(hostClient)} />);

    fireEvent.click(screen.getByRole("button", { name: "Puppeteering" }));
    fireEvent.change(screen.getByPlaceholderText("/path/to/lineart.png"), {
      target: { value: "/sprite.png" },
    });
    fireEvent.change(screen.getByPlaceholderText("10,20 80,25"), {
      target: { value: "10,20 80,25" },
    });
    fireEvent.change(screen.getByPlaceholderText("12,24 95,20"), {
      target: { value: "12,24 95,20" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Execute puppeteering/i }));

    await vi.waitFor(() => {
      expect(screen.getByText("Mesh Vertices: 57")).toBeInTheDocument();
    });
    expect(hostClient.csgArapDeform).toHaveBeenCalledWith({
      image_path: "/sprite.png",
      control_points: [
        [10, 20],
        [80, 25],
      ],
      target_points: [
        [12, 24],
        [95, 20],
      ],
    });
  });

  test("a failed solver payload surfaces the error", async () => {
    const hostClient = makeHostClient();
    hostClient.csgColorizeReference.mockResolvedValue({
      success: false,
      output_path: null,
      width: 0,
      height: 0,
      elapsed_seconds: 0,
      error: "solver diverged",
    });
    const showModal = vi.fn();
    render(<MangaWorkspaceView showModal={showModal} hostClient={asHostClient(hostClient)} />);

    fireEvent.change(screen.getByPlaceholderText("/path/to/lineart.png"), {
      target: { value: "/lineart.png" },
    });
    fireEvent.change(screen.getByPlaceholderText("/path/to/reference_palette.png"), {
      target: { value: "/palette.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Execute colorization/i }));

    await vi.waitFor(() => {
      expect(screen.getByText("Error: solver diverged")).toBeInTheDocument();
    });
    expect(showModal).toHaveBeenCalledWith("solver diverged", "error");
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

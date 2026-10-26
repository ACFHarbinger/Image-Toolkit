import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SlideshowPresenterWindow } from "./SlideshowPresenterWindow";
import type { HostClient } from "../hostclient";

afterEach(() => {
  cleanup();
});

describe("SlideshowPresenterWindow", () => {
  const fakeMonitors = [
    {
      id: "0",
      name: "Primary DP-1",
      width: 1920,
      height: 1080,
      x: 0,
      y: 0,
      is_primary: true,
    },
    {
      id: "1",
      name: "Secondary HDMI-1",
      width: 1920,
      height: 1080,
      x: 1920,
      y: 0,
      is_primary: false,
    },
  ];

  const fakeConfig = {
    interval_seconds: 180,
    style: "fill",
    monitor_queues: {
      "0": ["/path/to/pic1.jpg", "/path/to/pic2.png"],
      "1": ["/path/to/second.png"],
    },
    current_paths: {
      "0": "/path/to/pic1.jpg",
      "1": "/path/to/second.png",
    },
    config_path: "/home/user/.image-toolkit/.slideshow_config.json",
    elapsed_seconds: 0.01,
  };

  const createFakeClient = () => {
    return {
      wallpaperGetMonitors: vi.fn().mockResolvedValue({
        monitors: fakeMonitors,
        desktop_environment: "Linux (KDE)",
        elapsed_seconds: 0.01,
      }),
      wallpaperSlideshowConfig: vi.fn().mockResolvedValue(fakeConfig),
      wallpaperSlideshowToggle: vi.fn().mockResolvedValue({
        running: true,
        pid: 12345,
        message: "Slideshow daemon started",
        elapsed_seconds: 0.01,
      }),
      wallpaperSet: vi.fn().mockResolvedValue({
        success: true,
        message: "Applied wallpaper",
        applied_monitors: ["0"],
        elapsed_seconds: 0.02,
      }),
    } as unknown as HostClient;
  };

  it("loads monitors and queue without calling wallpaperSet on mount", async () => {
    const client = createFakeClient();
    render(<SlideshowPresenterWindow hostClient={client} />);

    await waitFor(() => {
      expect(client.wallpaperGetMonitors).toHaveBeenCalled();
      expect(client.wallpaperSlideshowConfig).toHaveBeenCalledWith({ update: false });
    });

    // CRITICAL: Desktop wallpaper must not be changed merely by opening the presenter window!
    expect(client.wallpaperSet).not.toHaveBeenCalled();

    // Check monitors and queue items appear
    expect(await screen.findByText(/Primary DP-1/)).toBeInTheDocument();
    expect(screen.getByText("pic1.jpg")).toBeInTheDocument();
    expect(screen.getByText("pic2.png")).toBeInTheDocument();
  });

  it("allows switching monitors and inspecting the selected queue", async () => {
    const client = createFakeClient();
    render(<SlideshowPresenterWindow hostClient={client} />);

    expect(await screen.findByText("pic1.jpg")).toBeInTheDocument();

    const monitor1Tab = screen.getByTestId("monitor-tab-1");
    fireEvent.click(monitor1Tab);

    expect(await screen.findByText("second.png")).toBeInTheDocument();
  });

  it("adds an image to the queue and persists config", async () => {
    const client = createFakeClient();
    render(<SlideshowPresenterWindow hostClient={client} />);

    await waitFor(() => {
      expect(screen.getByText("pic1.jpg")).toBeInTheDocument();
    });

    const input = screen.getByTestId("queue-path-input");
    fireEvent.change(input, { target: { value: "/new/wallpaper.jpg" } });

    const addBtn = screen.getByTestId("queue-add-button");
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(client.wallpaperSlideshowConfig).toHaveBeenCalledWith(
        expect.objectContaining({
          update: true,
          monitor_queues: expect.objectContaining({
            "0": ["/path/to/pic1.jpg", "/path/to/pic2.png", "/new/wallpaper.jpg"],
          }),
        }),
      );
    });
  });

  it("toggles the background slideshow daemon", async () => {
    const client = createFakeClient();
    render(<SlideshowPresenterWindow hostClient={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-slideshow-button")).toBeInTheDocument();
    });

    const toggleBtn = screen.getByTestId("toggle-slideshow-button");
    expect(toggleBtn).toHaveTextContent(/Start Slideshow/);

    fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(client.wallpaperSlideshowToggle).toHaveBeenCalledWith({ running: true });
    });

    expect(await screen.findByText(/Slideshow daemon started/)).toBeInTheDocument();
  });

  it("sets selected item as active desktop wallpaper explicitly on button click", async () => {
    const client = createFakeClient();
    render(<SlideshowPresenterWindow hostClient={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("set-active-1")).toBeInTheDocument();
    });

    // Click "Set Active" on item 1 (pic2.png)
    fireEvent.click(screen.getByTestId("set-active-1"));

    await waitFor(() => {
      expect(client.wallpaperSet).toHaveBeenCalledWith({
        path_map: { "0": "/path/to/pic2.png" },
        style: "fill",
      });
    });
  });
});

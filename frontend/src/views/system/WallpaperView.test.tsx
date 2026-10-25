import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { WallpaperView } from "./WallpaperView";

describe("WallpaperView", () => {
  afterEach(() => {
    cleanup();
  });

  const mockMonitorsResult = {
    desktop_environment: "KDE Plasma",
    monitors: [
      {
        id: "DP-1",
        name: "DisplayPort-1",
        width: 2560,
        height: 1440,
        x: 0,
        y: 0,
        is_primary: true,
      },
    ],
  };

  const mockConfigResult = {
    interval_seconds: 300,
    style: "fill",
    monitor_queues: {
      "DP-1": ["/home/user/wallpapers/nature.jpg"],
    },
    current_paths: {},
    config_path: "/home/user/.image-toolkit/.slideshow_config.json",
  };

  test("loads monitors and slideshow config on mount", async () => {
    const hostClient = {
      wallpaperGetMonitors: vi.fn().mockResolvedValue(mockMonitorsResult),
      wallpaperSlideshowConfig: vi.fn().mockResolvedValue(mockConfigResult),
      wallpaperSet: vi.fn(),
      wallpaperSlideshowToggle: vi.fn(),
    };

    render(<WallpaperView hostClient={hostClient as any} />);

    expect(await screen.findByText("KDE Plasma")).toBeInTheDocument();
    const monitors = await screen.findAllByText(/DisplayPort-1/i);
    expect(monitors.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/2560x1440/)).toBeInTheDocument();
    expect(hostClient.wallpaperGetMonitors).toHaveBeenCalledTimes(1);
    expect(hostClient.wallpaperSlideshowConfig).toHaveBeenCalledWith({ update: false });
  });

  test("applies static wallpaper configuration", async () => {
    const hostClient = {
      wallpaperGetMonitors: vi.fn().mockResolvedValue(mockMonitorsResult),
      wallpaperSlideshowConfig: vi.fn().mockResolvedValue(mockConfigResult),
      wallpaperSet: vi.fn().mockResolvedValue({
        success: true,
        message: "Wallpaper applied successfully",
        applied_monitors: ["DP-1"],
      }),
      wallpaperSlideshowToggle: vi.fn(),
    };

    render(<WallpaperView hostClient={hostClient as any} />);

    await screen.findByText("KDE Plasma");

    const pathInput = screen.getByPlaceholderText("/absolute/path/to/wallpaper.png");
    fireEvent.change(pathInput, { target: { value: "/home/user/wallpapers/sky.png" } });

    const applyButton = screen.getByRole("button", { name: /Apply Static Wallpaper/i });
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(hostClient.wallpaperSet).toHaveBeenCalledWith({
        path_map: { "DP-1": "/home/user/wallpapers/sky.png" },
        style: "fill",
        background_color: null,
      });
    });

    expect(await screen.findByText("Wallpaper applied successfully")).toBeInTheDocument();
  });

  test("starts and stops the slideshow daemon", async () => {
    const hostClient = {
      wallpaperGetMonitors: vi.fn().mockResolvedValue(mockMonitorsResult),
      wallpaperSlideshowConfig: vi.fn().mockResolvedValue(mockConfigResult),
      wallpaperSet: vi.fn(),
      wallpaperSlideshowToggle: vi.fn().mockResolvedValue({
        running: true,
        pid: 9999,
        message: "Slideshow daemon started",
      }),
    };

    render(<WallpaperView hostClient={hostClient as any} />);

    await screen.findByText("KDE Plasma");

    const toggleButton = screen.getByRole("button", { name: /Start Slideshow/i });
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(hostClient.wallpaperSlideshowToggle).toHaveBeenCalledWith({ running: true });
    });

    expect(await screen.findByText("Slideshow daemon started")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Stop Slideshow/i })).toBeInTheDocument();
  });

  test("updates slideshow configuration", async () => {
    const hostClient = {
      wallpaperGetMonitors: vi.fn().mockResolvedValue(mockMonitorsResult),
      wallpaperSlideshowConfig: vi.fn()
        .mockResolvedValueOnce(mockConfigResult)
        .mockResolvedValueOnce({
          ...mockConfigResult,
          interval_seconds: 600,
        }),
      wallpaperSet: vi.fn(),
      wallpaperSlideshowToggle: vi.fn(),
    };

    render(<WallpaperView hostClient={hostClient as any} />);

    await screen.findByText("KDE Plasma");

    const intervalInput = screen.getByDisplayValue("300");
    fireEvent.change(intervalInput, { target: { value: "600" } });

    const saveButton = screen.getByRole("button", { name: /Save Configuration/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(hostClient.wallpaperSlideshowConfig).toHaveBeenCalledWith({
        update: true,
        interval_seconds: 600,
        style: "fill",
        monitor_queues: {
          "DP-1": ["/home/user/wallpapers/nature.jpg"],
        },
        current_paths: {},
      });
    });

    expect(await screen.findByText("Slideshow configuration saved successfully")).toBeInTheDocument();
  });
});

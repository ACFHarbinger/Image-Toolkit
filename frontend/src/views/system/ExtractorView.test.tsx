import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ExtractorView } from "./ExtractorView";

afterEach(() => {
  cleanup();
});

test("probe shows the returned stream", async () => {
  const hostClient = {
    extractorProbe: vi.fn().mockResolvedValue({
      available: true,
      width: 320,
      height: 240,
      duration_seconds: 1.5,
      codec: "h264",
      error: "",
    }),
  };
  render(<ExtractorView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Video"), { target: { value: "/clip.mp4" } });
  fireEvent.click(screen.getByRole("button", { name: "Probe" }));
  expect(await screen.findByText("320x240 h264 1.5s")).toBeInTheDocument();
  expect(hostClient.extractorProbe).toHaveBeenCalledWith({ path: "/clip.mp4" });
});

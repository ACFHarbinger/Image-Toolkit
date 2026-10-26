import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MediaLoaderView } from "./MediaLoaderView";

afterEach(() => {
  cleanup();
});

test("plan does not download", async () => {
  const hostClient = {
    mediaLoaderPlan: vi.fn().mockResolvedValue({
      accepted: true,
      downloaded: false,
      url: "https://example.com/a.png",
      destination: "/tmp/in",
      reason: "download is not performed",
    }),
  };
  render(<MediaLoaderView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("URL"), { target: { value: "https://example.com/a.png" } });
  fireEvent.change(screen.getByLabelText("Destination"), { target: { value: "/tmp/in" } });
  fireEvent.click(screen.getByRole("button", { name: "Plan" }));
  expect(await screen.findByText("download is not performed")).toBeInTheDocument();
  expect(hostClient.mediaLoaderPlan).toHaveBeenCalledWith({
    url: "https://example.com/a.png",
    destination: "/tmp/in",
  });
});

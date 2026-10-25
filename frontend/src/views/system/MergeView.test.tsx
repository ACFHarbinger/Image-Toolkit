import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { MergeView } from "./MergeView";

afterEach(() => {
  cleanup();
});

test("concatenate sends the caller paths and output", async () => {
  const hostClient = {
    mergeConcatenate: vi.fn().mockResolvedValue({
      written: true,
      width: 4,
      height: 2,
      preview_png_base64: "",
      error: "",
    }),
  };
  render(<MergeView hostClient={hostClient} />);
  fireEvent.change(screen.getByLabelText("Images"), { target: { value: "/a.png\n/b.png" } });
  fireEvent.change(screen.getByPlaceholderText(/Output Filename/i), { target: { value: "/out.png" } });
  fireEvent.click(screen.getByRole("button", { name: "Concatenate" }));
  expect(await screen.findByRole("img", { name: "Merged preview" })).toBeInTheDocument();
  expect(hostClient.mergeConcatenate).toHaveBeenCalledWith({
    paths: ["/a.png", "/b.png"],
    output_path: "/out.png",
    direction: "horizontal",
    spacing: 0,
    align: "start",
  });
});

import { invoke } from "@tauri-apps/api/core";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { AppStoreProvider } from "../store/AppStoreProvider";

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.mocked(invoke).mockReset();
  vi.mocked(invoke).mockImplementation(() => Promise.resolve({}));
});

function renderLoggedIn() {
  localStorage.setItem("app_authenticated", "true");
  localStorage.setItem("app_account_name", "TestUser");
  return render(
    <AppStoreProvider>
      <App />
    </AppStoreProvider>,
  );
}

test("the rail opens catalog ids and the status bar shows the active id", async () => {
  renderLoggedIn();
  expect(await screen.findByText(/Image Database and Toolkit/i)).toBeInTheDocument();
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("system.convert");
  expect(await screen.findByTestId("convert-pilot")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Merge" }));
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("system.merge");
  expect(screen.getByPlaceholderText(/Output Filename/i)).toBeInTheDocument();
  expect(screen.queryByTestId("convert-pilot")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "category Image Stitching" }));
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("system.merge");
  expect(screen.queryByRole("button", { name: "Merge" })).not.toBeInTheDocument();
});

test("convert calls the shell HostClient over bridge_request", async () => {
  vi.mocked(invoke).mockImplementation(async (command: string, args?: unknown) => {
    if (command !== "bridge_request") {
      return {};
    }
    const request = (
      args as
        | {
            request?: {
              id?: string;
              method?: string;
              params?: { input_path?: string; output_path?: string; output_format?: string };
            };
          }
        | undefined
    )?.request;
    if (!request) {
      return {};
    }
    if (request.method === "system.handshake") {
      return {
        jsonrpc: "2.0",
        id: request.id,
        result: {
          protocol: "image-toolkit-bridge",
          version: "1.0.0",
          compatibility: { min: "1.0.0", max: "1.0.0" },
          capabilities: ["system", "jobs", "convert"],
        },
      };
    }
    return {
      jsonrpc: "2.0",
      id: request.id,
      result: {
        input_path: request.params?.input_path,
        output_path: "/tmp/out.png",
        success: true,
      },
    };
  });
  renderLoggedIn();
  const pilot = await screen.findByTestId("convert-pilot");
  fireEvent.change(pilot.querySelectorAll("input")[0], { target: { value: "/pics/a.png" } });
  fireEvent.change(pilot.querySelectorAll("input")[1], { target: { value: "/tmp/out.jpg" } });
  fireEvent.click(pilot.querySelector("button") as HTMLButtonElement);
  expect(await screen.findByText("Status: ok")).toBeInTheDocument();
  await waitFor(() => {
    const convert = vi.mocked(invoke).mock.calls
      .filter((call) => call[0] === "bridge_request")
      .map(
        (call) =>
          (
            call[1] as {
              request: { method: string; params?: { output_path?: string; output_format?: string } };
            }
          ).request,
      )
      .find((request) => request.method === "convert.convert");
    expect(convert?.params?.output_format).toBe("jpg");
    expect(convert?.params?.output_path).toBe("/tmp/out.jpg");
  });
});

test("a workspace paints its ribbon, and the inspector reads the catalog entry", async () => {
  renderLoggedIn();
  await screen.findByTestId("convert-pilot");
  fireEvent.click(screen.getByRole("button", { name: "category Image Stitching" }));
  fireEvent.click(screen.getByRole("button", { name: "Image Stitching" }));
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("stitch");
  expect(screen.getByRole("button", { name: "Canvas" })).toHaveAttribute(
    "data-catalog-id",
    "stitch.canvas",
  );
  fireEvent.click(screen.getByRole("button", { name: "Canvas" }));
  expect(screen.getByTestId("unported-view")).toHaveTextContent("stitch.canvas");

  fireEvent.click(screen.getByRole("button", { name: "Toggle inspector" }));
  expect(screen.getByTestId("inspector-body")).toHaveTextContent("stitch.canvas");
  expect(screen.getByTestId("active-window-role")).toHaveTextContent("main");
});

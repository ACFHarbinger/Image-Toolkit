import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import App from "../App";
import { AppStoreProvider } from "../store/AppStoreProvider";

afterEach(() => {
  cleanup();
  localStorage.clear();
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
  expect(await screen.findByText("Convert Settings")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Merge" }));
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("system.merge");
  expect(screen.getByPlaceholderText(/Output Filename/i)).toBeInTheDocument();
  expect(screen.queryByText("Convert Settings")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "category Image Stitching" }));
  expect(screen.getByTestId("active-catalog-id")).toHaveTextContent("system.merge");
  expect(screen.queryByRole("button", { name: "Merge" })).not.toBeInTheDocument();
});

test("a workspace paints its ribbon, and the inspector reads the catalog entry", async () => {
  renderLoggedIn();
  await screen.findByText("Convert Settings");
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

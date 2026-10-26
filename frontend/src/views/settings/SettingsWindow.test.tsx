import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { SettingsWindow } from "./SettingsWindow";

const REASON = "credentials stay on the C++ vault session";
const SECTIONS = ["appearance", "profiles", "shortcuts", "tab_config", "credentials", "reset"];

afterEach(() => {
  cleanup();
});

test("renders the six described sections and does not submit a password", async () => {
  const hostClient = {
    prefsDescribe: vi.fn().mockResolvedValue({
      sections: SECTIONS,
      credentials_changed: false,
      reason: REASON,
    }),
  };
  render(<SettingsWindow hostClient={hostClient} account="ada" onClose={() => {}} />);

  expect(await screen.findByRole("tab", { name: "credentials" })).toBeInTheDocument();
  for (const section of SECTIONS) {
    expect(screen.getByRole("tab", { name: section })).toBeInTheDocument();
  }
  expect(hostClient.prefsDescribe).toHaveBeenCalledWith("ada");

  fireEvent.click(screen.getByRole("tab", { name: "credentials" }));
  expect(screen.getByRole("tabpanel").textContent).toContain(REASON);
  fireEvent.click(screen.getByRole("tab", { name: "reset" }));
  expect(screen.getByRole("tabpanel").textContent).toContain(REASON);

  expect(document.querySelector('input[type="password"]')).toBeNull();
  expect(screen.queryByRole("button", { name: /save|submit|update password/i })).toBeNull();
});

test("surfaces an empty account as an error", async () => {
  const hostClient = {
    prefsDescribe: vi.fn().mockRejectedValue(new Error("account is required")),
  };
  render(<SettingsWindow hostClient={hostClient} account="" onClose={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("account is required");
  expect(document.querySelector('input[type="password"]')).toBeNull();
});

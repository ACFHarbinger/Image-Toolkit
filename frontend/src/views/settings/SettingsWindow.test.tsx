import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { PrefsGetResult, PrefsSetParams, PrefsSetResult } from "../../../../contracts/generated/ts/prefs";
import { SettingsWindow } from "./SettingsWindow";

const LOCKED = "C++ vault session locked";

const SHORTCUT = {
  id: "gallery.select_all",
  description: "Select all images on current page",
  scope: "Gallery",
  default: "Ctrl+A",
  custom: "",
};

function loaded(): PrefsGetResult {
  return {
    account: "ada",
    profiles: { startup_category: "System Tools", startup_tab: "" },
    gallery: { thumbnail_size: 180, page_size: 100, confirm_deletions: true, recursive_scan: true },
    logging: { level: "INFO", file_logging: false },
    shortcuts: [SHORTCUT],
  };
}

afterEach(() => {
  cleanup();
});

test("loads values, saves edits, and shows the saved document", async () => {
  let saved: PrefsSetParams | undefined;
  const hostClient = {
    prefsGet: vi.fn().mockResolvedValue(loaded()),
    prefsSet: vi.fn(async (params: PrefsSetParams): Promise<PrefsSetResult> => {
      saved = params;
      return {
        success: true,
        reason: "",
        credentials_changed: false,
        account: "ada",
        profiles: { startup_category: params.profiles.startup_category, startup_tab: "Stitch" },
        gallery: { ...params.gallery, page_size: 150 },
        logging: params.logging,
        shortcuts: [{ ...SHORTCUT, custom: params.shortcut?.chord ?? "" }],
      };
    }),
  };
  render(<SettingsWindow hostClient={hostClient} account="ada" onClose={() => {}} />);

  expect(await screen.findByLabelText("Account name")).toHaveValue("ada");
  expect(hostClient.prefsGet).toHaveBeenCalledWith("ada");
  expect(screen.getByLabelText("Account name")).toHaveValue("ada");

  fireEvent.click(screen.getByRole("tab", { name: "Profiles" }));
  fireEvent.change(screen.getByLabelText("Startup category"), { target: { value: "Manga" } });
  fireEvent.change(screen.getByLabelText("Startup tab"), { target: { value: "Merge" } });

  fireEvent.click(screen.getByRole("tab", { name: "Gallery" }));
  expect(screen.getByLabelText("Thumbnail size")).toHaveValue(180);
  fireEvent.change(screen.getByLabelText("Thumbnail size"), { target: { value: "200" } });
  fireEvent.click(screen.getByLabelText("Confirm deletions"));
  fireEvent.click(screen.getByLabelText("Recursive scan"));

  fireEvent.click(screen.getByRole("tab", { name: "Logging" }));
  fireEvent.change(screen.getByLabelText("Log level"), { target: { value: "WARNING" } });
  fireEvent.click(screen.getByLabelText("File logging"));

  fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));
  expect(screen.getByRole("list", { name: "Shortcut actions" })).toHaveTextContent("Select all images on current page");
  fireEvent.change(screen.getByLabelText("Shortcut chord"), { target: { value: "Meta+A" } });

  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(saved?.gallery.thumbnail_size).toBe(200);
  });
  expect(saved?.profiles).toEqual({ startup_category: "Manga", startup_tab: "Merge" });
  expect(saved?.gallery.confirm_deletions).toBe(false);
  expect(saved?.gallery.recursive_scan).toBe(false);
  expect(saved?.logging).toEqual({ level: "WARNING", file_logging: true });
  expect(saved?.shortcut).toEqual({ action: "gallery.select_all", chord: "Meta+A" });

  fireEvent.click(screen.getByRole("tab", { name: "Profiles" }));
  expect(screen.getByLabelText("Startup category")).toHaveValue("Manga");
  expect(screen.getByLabelText("Startup tab")).toHaveValue("Stitch");
  fireEvent.click(screen.getByRole("tab", { name: "Gallery" }));
  expect(screen.getByLabelText("Thumbnail size")).toHaveValue(200);
  expect(screen.getByLabelText("Page size")).toHaveValue(150);
  fireEvent.click(screen.getByRole("tab", { name: "Logging" }));
  expect(screen.getByLabelText("Log level")).toHaveValue("WARNING");
  expect(screen.getByLabelText("File logging")).toBeChecked();
  fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));
  expect(screen.getByLabelText("Shortcut chord")).toHaveValue("Meta+A");
  expect(screen.getByRole("list", { name: "Shortcut actions" })).toHaveTextContent("Meta+A");
});

test("a new master password is sent and a locked session is shown", async () => {
  const hostClient = {
    prefsGet: vi.fn().mockResolvedValue(loaded()),
    prefsSet: vi.fn(
      async (params: PrefsSetParams): Promise<PrefsSetResult> => ({
        success: false,
        reason: LOCKED,
        credentials_changed: false,
        account: "ada",
        profiles: params.profiles,
        gallery: params.gallery,
        logging: params.logging,
        shortcuts: [SHORTCUT],
      }),
    ),
  };
  render(<SettingsWindow hostClient={hostClient} account="ada" onClose={() => {}} />);
  expect(await screen.findByLabelText("New master password")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "old-secret" } });
  fireEvent.change(screen.getByLabelText("New master password"), { target: { value: "new-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(screen.getByRole("status")).toHaveTextContent(LOCKED);
  });
  const params = hostClient.prefsSet.mock.calls[0][0] as PrefsSetParams;
  expect(params.current_password).toBe("old-secret");
  expect(params.new_password).toBe("new-secret");
  expect(screen.getByLabelText("New master password")).toHaveValue("");
  expect(screen.getByLabelText("Current password")).toHaveValue("");
});

test("surfaces an empty account as an error without a password field", async () => {
  const hostClient = {
    prefsGet: vi.fn().mockRejectedValue(new Error("account is required")),
    prefsSet: vi.fn(),
  };
  render(<SettingsWindow hostClient={hostClient} account="" onClose={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("account is required");
  expect(document.querySelector('input[type="password"]')).toBeNull();
  expect(hostClient.prefsSet).not.toHaveBeenCalled();
});

test("an unknown shortcut action stays on the form as an error", async () => {
  const hostClient = {
    prefsGet: vi.fn().mockResolvedValue(loaded()),
    prefsSet: vi.fn().mockRejectedValue(new Error("unknown action")),
  };
  render(<SettingsWindow hostClient={hostClient} account="ada" onClose={() => {}} />);
  await screen.findByLabelText("Account name");
  fireEvent.click(screen.getByRole("tab", { name: "Shortcuts" }));
  fireEvent.change(screen.getByLabelText("Shortcut chord"), { target: { value: "Meta+A" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("unknown action");
  expect(screen.getByLabelText("Shortcut chord")).toHaveValue("Meta+A");
});

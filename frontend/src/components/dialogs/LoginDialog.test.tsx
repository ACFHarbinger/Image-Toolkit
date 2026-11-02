import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { AppStoreProvider } from "../../store/AppStoreProvider";
import { LoginDialog, type AuthBridge, type SessionClient } from "./LoginDialog";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

function renderDialog(session: SessionClient, authClient: AuthBridge) {
  return render(
    <AppStoreProvider>
      <LoginDialog session={session} authClient={authClient} />
    </AppStoreProvider>,
  );
}

function openBridge(unlocked = true): AuthBridge {
  return {
    authUnlock: vi.fn().mockResolvedValue({
      success: unlocked,
      account: "keeper",
      message: unlocked ? "C++ vault session open." : "Invalid password.",
    }),
    authStatus: vi.fn().mockResolvedValue({
      unlocked,
      account: "keeper",
      reason: unlocked ? "C++ vault session open" : "C++ vault session locked",
    }),
  };
}

test("login unlocks through the sidecar and remembers only the account name", async () => {
  const session: SessionClient = { create: vi.fn() };
  const authClient = openBridge();
  renderDialog(session, authClient);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: " keeper " } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  await waitFor(() => expect(localStorage.getItem("app_account_name")).toBe("keeper"));
  expect(localStorage.getItem("app_authenticated")).toBeNull();
  expect(authClient.authUnlock).toHaveBeenCalledWith({ account: "keeper", password: "secret" });
  expect(authClient.authStatus).toHaveBeenCalledWith({ account: "keeper" });
  expect(session.create).not.toHaveBeenCalled();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("a rejected unlock shows the message and does not store the account", async () => {
  const session: SessionClient = { create: vi.fn() };
  const authClient = openBridge(false);
  renderDialog(session, authClient);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "keeper" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Invalid password.");
  expect(localStorage.getItem("app_account_name")).toBeNull();
  expect(authClient.authStatus).not.toHaveBeenCalled();
});

test("create account uses the vault create flow, then the sidecar session", async () => {
  const session: SessionClient = {
    create: vi.fn().mockResolvedValue({ success: true, message: "Account 'keeper' created." }),
  };
  const authClient = openBridge();
  renderDialog(session, authClient);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "keeper" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Create Account" }));
  await waitFor(() => expect(session.create).toHaveBeenCalledWith("keeper", "secret"));
  await waitFor(() => expect(authClient.authUnlock).toHaveBeenCalledWith({ account: "keeper", password: "secret" }));
  await waitFor(() => expect(localStorage.getItem("app_account_name")).toBe("keeper"));
  expect(localStorage.getItem("app_authenticated")).toBeNull();
});

test("an empty account is not sent", async () => {
  const session: SessionClient = { create: vi.fn() };
  const authClient = openBridge();
  renderDialog(session, authClient);
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Please enter an account name");
  expect(authClient.authUnlock).not.toHaveBeenCalled();
});

test("an empty password is not sent", async () => {
  const session: SessionClient = { create: vi.fn() };
  const authClient = openBridge();
  renderDialog(session, authClient);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "keeper" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Please enter a password");
  expect(authClient.authUnlock).not.toHaveBeenCalled();
});

function guestBridge(overrides: Partial<AuthBridge> = {}): AuthBridge {
  return {
    ...openBridge(),
    authGuest: vi.fn().mockImplementation(async ({ username }: { username?: string | null }) => ({
      success: true,
      account: username || "guest_ab12cd34",
      anonymous: !username,
      message: "Guest session open.",
    })),
    ...overrides,
  };
}

function enterGuestMode() {
  fireEvent.click(screen.getByRole("button", { name: "Guest Mode" }));
}

test("guest mode hides the password, logs in anonymously and is never remembered", async () => {
  const authClient = guestBridge();
  renderDialog({ create: vi.fn() }, authClient);
  enterGuestMode();
  expect(screen.queryByLabelText("Password")).toBeNull();
  expect(screen.getByPlaceholderText("Username (optional for anonymous login)")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Login Anonymously" }));
  await waitFor(() => expect(authClient.authGuest).toHaveBeenCalledWith({ username: null }));
  expect(authClient.authUnlock).not.toHaveBeenCalled();
  expect(localStorage.getItem("app_account_name")).toBeNull();
});

test("login as guest sends the trimmed name, and an empty name is anonymous", async () => {
  const authClient = guestBridge();
  renderDialog({ create: vi.fn() }, authClient);
  enterGuestMode();
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "  Rui " } });
  fireEvent.click(screen.getByRole("button", { name: "Login as Guest" }));
  await waitFor(() => expect(authClient.authGuest).toHaveBeenCalledWith({ username: "Rui" }));
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "   " } });
  fireEvent.click(screen.getByRole("button", { name: "Login as Guest" }));
  await waitFor(() => expect(authClient.authGuest).toHaveBeenLastCalledWith({ username: null }));
});

test("the toggle returns to account access and a failed guest start shows the message", async () => {
  const authClient = guestBridge({
    authGuest: vi.fn().mockResolvedValue({ success: false, account: "g", anonymous: true, message: "Failed to start the guest session." }),
  });
  renderDialog({ create: vi.fn() }, authClient);
  enterGuestMode();
  fireEvent.click(screen.getByRole("button", { name: "Login Anonymously" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Failed to start the guest session.");
  fireEvent.click(screen.getByRole("button", { name: "Account Access" }));
  expect(screen.getByLabelText("Password")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("guest mode is unavailable on a bridge without it", async () => {
  renderDialog({ create: vi.fn() }, openBridge());
  enterGuestMode();
  fireEvent.click(screen.getByRole("button", { name: "Login Anonymously" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Guest mode is unavailable.");
});

function profileBridge(): AuthBridge {
  return {
    authUnlock: vi.fn().mockResolvedValue({
      success: true,
      account: "keeper",
      message: "C++ vault session open.",
      profiles: ["Night", "Alpha"],
      credentials: ["google_api_key"],
    }),
    authStatus: vi.fn().mockResolvedValue({ unlocked: true, account: "keeper", reason: "C++ vault session open" }),
    authApplyProfile: vi.fn().mockResolvedValue({
      success: true,
      account: "keeper",
      profile: "Night",
      message: "Applied 'Night'.",
      theme: "light",
      tab_configurations: { merge: { engine: "orb" } },
    }),
  };
}

function signIn() {
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "keeper" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
}

test("saved profiles open a picker in the Qt order with Previous Profile selected", async () => {
  const authClient = profileBridge();
  renderDialog({ create: vi.fn() }, authClient);
  signIn();
  const radios = await screen.findAllByRole("radio");
  expect(radios.map((r) => (r as HTMLInputElement).value)).toEqual(["Default", "Previous Profile", "Alpha", "Night"]);
  expect((screen.getByRole("radio", { name: "Previous Profile" }) as HTMLInputElement).checked).toBe(true);
  expect(localStorage.getItem("app_account_name")).toBeNull();
});

test("applying a profile asks the sidecar, applies theme and tab settings, then signs in", async () => {
  const authClient = profileBridge();
  renderDialog({ create: vi.fn() }, authClient);
  signIn();
  fireEvent.click(await screen.findByRole("radio", { name: "Night" }));
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));
  await waitFor(() => expect(authClient.authApplyProfile).toHaveBeenCalledWith({ account: "keeper", profile: "Night" }));
  await waitFor(() => expect(localStorage.getItem("app_account_name")).toBe("keeper"));
  expect(JSON.parse(localStorage.getItem("app_preferences") ?? "{}")).toMatchObject({
    theme: "light",
    tabConfigurations: { merge: { engine: "orb" } },
  });
});

test("skipping the picker signs in without applying anything", async () => {
  const authClient = profileBridge();
  renderDialog({ create: vi.fn() }, authClient);
  signIn();
  fireEvent.click(await screen.findByRole("button", { name: "Skip" }));
  await waitFor(() => expect(localStorage.getItem("app_account_name")).toBe("keeper"));
  expect(authClient.authApplyProfile).not.toHaveBeenCalled();
});

test("a refused profile keeps the picker open and shows the reason", async () => {
  const authClient = profileBridge();
  authClient.authApplyProfile = vi.fn().mockResolvedValue({
    success: false,
    account: "keeper",
    profile: "Night",
    message: "Unknown preference profile.",
    theme: "dark",
    tab_configurations: {},
  });
  renderDialog({ create: vi.fn() }, authClient);
  signIn();
  fireEvent.click(await screen.findByRole("button", { name: "Apply" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unknown preference profile.");
  expect(screen.getAllByRole("radio").length).toBe(4);
  expect(localStorage.getItem("app_account_name")).toBeNull();
});

test("an account without profiles signs in directly", async () => {
  const authClient = openBridge();
  renderDialog({ create: vi.fn() }, authClient);
  signIn();
  await waitFor(() => expect(localStorage.getItem("app_account_name")).toBe("keeper"));
  expect(screen.queryAllByRole("radio").length).toBe(0);
});

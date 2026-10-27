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

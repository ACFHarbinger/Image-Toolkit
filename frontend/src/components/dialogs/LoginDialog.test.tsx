import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { AppStoreProvider } from "../../store/AppStoreProvider";
import { LoginDialog, type AuthStatusClient } from "./LoginDialog";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

function renderDialog(client: AuthStatusClient) {
  return render(
    <AppStoreProvider>
      <LoginDialog authClient={client} />
    </AppStoreProvider>,
  );
}

test("login shows the locked reason and does not send the password", async () => {
  const client: AuthStatusClient = {
    authStatus: vi.fn().mockResolvedValue({
      unlocked: false,
      account: "keeper",
      reason: "unlock stays on the C++ session",
    }),
  };
  renderDialog(client);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: " keeper " } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("unlock stays on the C++ session");
  expect(client.authStatus).toHaveBeenCalledWith({ account: "keeper" });
  expect(localStorage.getItem("app_authenticated")).toBeNull();
});

test("create account is the same locked result", async () => {
  const client: AuthStatusClient = {
    authStatus: vi.fn().mockResolvedValue({
      unlocked: false,
      account: "keeper",
      reason: "unlock stays on the C++ session",
    }),
  };
  renderDialog(client);
  fireEvent.change(screen.getByLabelText("Account Name"), { target: { value: "keeper" } });
  fireEvent.click(screen.getByRole("button", { name: "Create Account" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("unlock stays on the C++ session");
  expect(client.authStatus).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem("app_authenticated")).toBeNull();
});

test("an empty account is not sent", async () => {
  const client: AuthStatusClient = {
    authStatus: vi.fn(),
  };
  renderDialog(client);
  fireEvent.click(screen.getByRole("button", { name: "Login" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Please enter an account name");
  expect(client.authStatus).not.toHaveBeenCalled();
});

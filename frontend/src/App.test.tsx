import React from "react";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { AppStoreProvider } from "./store/AppStoreProvider";

test("renders app title when logged in", async () => {
  localStorage.setItem("app_authenticated", "true");
  localStorage.setItem("app_account_name", "TestUser");
  render(
    <AppStoreProvider>
      <App />
    </AppStoreProvider>
  );
  const titleElement = await screen.findByText(/Image Database and Toolkit/i);
  expect(titleElement).toBeInTheDocument();
});

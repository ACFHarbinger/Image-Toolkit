import { expect, test } from "@playwright/test";

test("the Vite build logs in through the contract mock", async ({ page }) => {
  await page.addInitScript(() => {
    const host = window as unknown as {
      __TAURI_INTERNALS__: { invoke: (cmd: string) => Promise<unknown> };
    };
    host.__TAURI_INTERNALS__ = {
      invoke: async (cmd: string) => {
        if (cmd === "authenticate_user") {
          return { success: true, profiles: [] };
        }
        return {};
      },
    };
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Account Name" }).fill("parity");
  await page.getByRole("textbox", { name: "Password" }).fill("secret");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByTestId("convert-pilot")).toBeVisible();
});

import { expect, test } from "@playwright/test";

test("login opens the shell after the sidecar vault session is open", async ({ page }) => {
  await page.addInitScript(() => {
    const host = window as unknown as {
      __TAURI_INTERNALS__: {
        invoke: (cmd: string, args?: { request?: { id?: string; method?: string } }) => Promise<unknown>;
      };
    };
    host.__TAURI_INTERNALS__ = {
      invoke: async (cmd: string, args?: { request?: { id?: string; method?: string } }) => {
        if (cmd !== "bridge_request") {
          return {};
        }
        const request = args?.request;
        const id = request?.id ?? null;
        if (request?.method === "auth.unlock") {
          return {
            jsonrpc: "2.0",
            id,
            result: { success: true, account: "parity", message: "C++ vault session open." },
          };
        }
        if (request?.method === "auth.status") {
          return {
            jsonrpc: "2.0",
            id,
            result: { unlocked: true, account: "parity", reason: "C++ vault session open" },
          };
        }
        return {
          jsonrpc: "2.0",
          id,
          result: {
            protocol: "image-toolkit-bridge",
            version: "1.0.0",
            compatibility: { min: "1.0.0", max: "1.0.0" },
            capabilities: ["auth", "system", "convert"],
          },
        };
      },
    };
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Account Name" }).fill("parity");
  await page.getByRole("textbox", { name: "Password" }).fill("secret");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByTestId("convert-pilot")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Convert" })).toBeVisible();
});

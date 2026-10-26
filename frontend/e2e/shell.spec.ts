import { expect, test } from "@playwright/test";

test("the Vite build shows the locked session through the contract mock", async ({ page }) => {
  await page.addInitScript(() => {
    const host = window as unknown as {
      __TAURI_INTERNALS__: {
        invoke: (cmd: string, args?: { request?: { id?: string; method?: string; params?: { account?: string } } }) => Promise<unknown>;
      };
    };
    host.__TAURI_INTERNALS__ = {
      invoke: async (cmd: string, args?: { request?: { id?: string; method?: string; params?: { account?: string } } }) => {
        if (cmd !== "bridge_request") {
          return {};
        }
        const request = args?.request;
        if (request?.method === "auth.status") {
          return {
            jsonrpc: "2.0",
            id: request.id ?? null,
            result: {
              unlocked: false,
              account: request.params?.account ?? "",
              reason: "unlock stays on the C++ session",
            },
          };
        }
        return {
          jsonrpc: "2.0",
          id: request?.id ?? null,
          result: {
            protocol: "image-toolkit-bridge",
            version: "1.0.0",
            compatibility: { min: "1.0.0", max: "1.0.0" },
            capabilities: ["auth"],
          },
        };
      },
    };
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Account Name" }).fill("parity");
  await page.getByRole("textbox", { name: "Password" }).fill("secret");
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page.getByRole("alert")).toHaveText("unlock stays on the C++ session");
  await expect(page.getByTestId("convert-pilot")).toHaveCount(0);
});

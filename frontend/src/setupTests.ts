// jest-dom adds custom matchers for asserting on DOM nodes.
// allows you to do things like expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn().mockImplementation(() => Promise.resolve({})),
  convertFileSrc: vi.fn((path: string) => path),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockImplementation(() => Promise.resolve(() => {})),
  emit: vi.fn().mockImplementation(() => Promise.resolve({})),
}));

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn().mockImplementation(() => Promise.resolve(null)),
  save: vi.fn().mockImplementation(() => Promise.resolve(null)),
}));

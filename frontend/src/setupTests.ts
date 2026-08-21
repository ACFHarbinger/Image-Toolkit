// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import "@testing-library/jest-dom";

jest.mock("@tauri-apps/api/core", () => ({
  invoke: jest.fn().mockImplementation(() => Promise.resolve({})),
  convertFileSrc: jest.fn((path: string) => path),
}));

jest.mock("@tauri-apps/api/event", () => ({
  listen: jest.fn().mockImplementation(() => Promise.resolve(() => {})),
  emit: jest.fn().mockImplementation(() => Promise.resolve({})),
}));

jest.mock("@tauri-apps/plugin-dialog", () => ({
  open: jest.fn().mockImplementation(() => Promise.resolve(null)),
}));

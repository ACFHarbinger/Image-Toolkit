// src/api.ts
const API = "http://127.0.0.1:8000/api";

export const api = {
  get: <T>(endpoint: string): Promise<T> =>
    fetch(`${API}${endpoint}`).then((r) => r.json()),

  post: <T>(endpoint: string, data: unknown): Promise<T> =>
    fetch(`${API}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => r.json()),
};

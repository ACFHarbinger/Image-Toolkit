// src/api.js
const API = 'http://127.0.0.1:8000/api';

export const api = {
  get: (endpoint) => fetch(`${API}${endpoint}`).then(r => r.json()),
  post: (endpoint, data) => fetch(`${API}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(r => r.json()),
};
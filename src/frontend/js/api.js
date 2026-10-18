// Thin wrapper around fetch for the SpeakQuest REST API (served under /api by FastAPI).

const API_BASE = "/api";

export async function apiRequest(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data?.detail ?? `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export function getHealth() {
  return apiRequest("/health");
}

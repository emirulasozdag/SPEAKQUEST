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
    throw new ApiError(response.status, data?.detail);
  }
  return data;
}

// detail is a string for most errors, or a list of field errors for validation (422) responses
export class ApiError extends Error {
  constructor(status, detail) {
    const message = Array.isArray(detail)
      ? detail.map((error) => error.msg).join(" ")
      : detail ?? `Request failed with status ${status}`;
    super(message);
    this.status = status;
    this.fieldErrors = Array.isArray(detail) ? detail : [];
  }
}

export function registerUser(email, password) {
  return apiRequest("/auth/register", { method: "POST", body: { email, password } });
}

export function loginUser(email, password) {
  return apiRequest("/auth/login", { method: "POST", body: { email, password } });
}

export function getCurrentUser(token) {
  return apiRequest("/auth/me", { token });
}

export function getHealth() {
  return apiRequest("/health");
}

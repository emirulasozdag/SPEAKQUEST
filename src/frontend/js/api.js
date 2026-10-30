// Thin wrapper around fetch for the SpeakQuest REST API (served under /api by FastAPI).

import { showToast } from "./components/toast.js";
import { clearSession, getSession } from "./state.js";

const API_BASE = "/api";
export const LOGIN_PAGE = "/pages/login.html";

export async function apiRequest(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only throws when the server cannot be reached at all
    throw new ApiError(0, "The server could not be reached.");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, data?.detail);
  }
  return data;
}

// For endpoints that need a logged-in player. An expired or invalid session ends here:
// the player is sent back to the login page.
export async function authRequest(path, options = {}) {
  try {
    return await apiRequest(path, { ...options, token: getSession().token });
  } catch (error) {
    if (error.status === 401) {
      redirectToLogin();
    }
    throw error;
  }
}

export function redirectToLogin() {
  clearSession();
  window.location.assign(LOGIN_PAGE);
}

// The one place that turns API errors into feedback for the player.
// Validation errors (422) are handed back to the page so it can show them next to the fields.
export function handleApiError(error, { onFieldErrors } = {}) {
  if (!(error instanceof ApiError)) {
    console.error(error);
    showToast("Something went wrong. Please try again.");
  } else if (error.status === 401) {
    redirectToLogin();
  } else if (error.status === 422 && onFieldErrors) {
    onFieldErrors(error.fieldErrors);
  } else if (error.status === 501) {
    showToast("This feature is coming soon.");
  } else if (error.status === 0) {
    showToast("The server could not be reached. Check that it is running and try again.");
  } else {
    showToast(error.message);
  }
}

// detail is a string for most errors, or a list of field errors for validation (422) responses.
// status is 0 when the server could not be reached.
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

export function getCurrentUser() {
  return authRequest("/auth/me");
}

export function deleteAccount(password) {
  return authRequest("/auth/me", { method: "DELETE", body: { password } });
}

export function getProfile() {
  return authRequest("/player/profile");
}

export function saveProfile(profile) {
  return authRequest("/player/profile", { method: "PUT", body: profile });
}

export function getHealth() {
  return apiRequest("/health");
}

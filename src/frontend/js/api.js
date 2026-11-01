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

export function changePassword(currentPassword, newPassword) {
  return authRequest("/auth/change-password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export function resetProgress() {
  return authRequest("/player/reset", { method: "POST" });
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

export function getLocations() {
  return authRequest("/locations");
}

export function getQuests() {
  return authRequest("/quests");
}

// Resolves to null when the player has no active quest (the API answers 404)
export async function getActiveQuest() {
  try {
    return await authRequest("/quests/active");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function startQuest(questId) {
  return authRequest(`/quests/${questId}/start`, { method: "POST" });
}

export function completeQuest(questId) {
  return authRequest(`/quests/${questId}/complete`, { method: "POST" });
}

export function getDialogueHistory(questId) {
  return authRequest(`/dialogue/history/${questId}`);
}

export function getDialogueSummary(questId) {
  return authRequest(`/dialogue/summary/${questId}`);
}

export function sendDialogueMessage(message) {
  return authRequest("/dialogue/message", { method: "POST", body: { message } });
}

export function getDecisions(questId) {
  return authRequest(`/story/decisions/${questId}`);
}

export function makeDecision(questId, decisionId, optionId) {
  return authRequest("/story/decision", {
    method: "POST",
    body: { quest_id: questId, decision_id: decisionId, option_id: optionId },
  });
}

// Resolves to null while the story goes on (the API answers 404)
export async function getStoryEnding() {
  try {
    return await authRequest("/story/ending");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function getSkills() {
  return authRequest("/learning/skills");
}

export function getLearningErrors(limit = 100) {
  return authRequest(`/learning/errors?limit=${limit}`);
}

export function getLearningTimeline() {
  return authRequest("/learning/timeline");
}

export function getRecommendations() {
  return authRequest("/learning/recommendations");
}

export function getHealth() {
  return apiRequest("/health");
}

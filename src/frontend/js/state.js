// Minimal client-side state: session token and cached player profile.
// The backend stays the source of truth; this only avoids refetching on every page.

const STORAGE_KEY = "speakquest.session";

function read() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? {};
  } catch {
    return {};
  }
}

function write(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage can be unavailable (private mode); the app still works without it.
  }
}

export function getSession() {
  return read();
}

// A session is valid while its access token has not expired.
export function hasValidSession() {
  const { token, tokenExpiresAt } = read();
  return Boolean(token) && Date.now() < (tokenExpiresAt ?? 0);
}

export function setSession(partial) {
  write({ ...read(), ...partial });
}

export function clearSession() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clear.
  }
}

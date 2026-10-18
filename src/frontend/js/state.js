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

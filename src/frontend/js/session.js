// Login flow shared by the login and register pages.

import { ApiError, getCurrentUser, getProfile, loginUser } from "./api.js";
import { setSession } from "./state.js";

export const DASHBOARD_PAGE = "/pages/dashboard.html";
export const CHARACTER_PAGE = "/pages/character.html";

// Exchanges email and password for a token and stores the session.
export async function logIn(email, password) {
  const { access_token: token, expires_in: expiresIn } = await loginUser(email, password);
  setSession({ token, tokenExpiresAt: Date.now() + expiresIn * 1000 });

  const user = await getCurrentUser();
  setSession({ email: user.email, userId: user.id });
}

// Players without a character create one first; everyone else goes to the dashboard.
export async function pageAfterLogin() {
  try {
    await getProfile();
    return DASHBOARD_PAGE;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return CHARACTER_PAGE;
    }
    throw error;
  }
}

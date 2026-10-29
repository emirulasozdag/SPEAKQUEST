// Character creation: the step after registering. Saves the character and opens the dashboard.

import { ApiError, getProfile, handleApiError } from "../api.js";
import { saveCharacterForm } from "../components/character-form.js";
import { clearErrorsOnEdit } from "../components/form.js";
import { DASHBOARD_PAGE } from "../session.js";

const form = document.querySelector("#character-form");
const alertBox = document.querySelector("#character-alert");
const submitButton = form.querySelector('button[type="submit"]');

// A player who already has a character goes straight to the game.
async function skipIfCharacterExists() {
  try {
    await getProfile();
    window.location.replace(DASHBOARD_PAGE);
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) {
      handleApiError(error);
    }
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "Moving in…";

  const profile = await saveCharacterForm(form, alertBox);
  if (profile) {
    window.location.assign(DASHBOARD_PAGE);
    return;
  }
  submitButton.disabled = false;
  submitButton.textContent = "Move to the city";
});

clearErrorsOnEdit(form);
skipIfCharacterExists();

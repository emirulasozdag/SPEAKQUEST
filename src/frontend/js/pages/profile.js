// Profile page: shows the saved character and account email, and saves character changes.

import { ApiError, getCurrentUser, getProfile, handleApiError } from "../api.js";
import { fillCharacterForm, saveCharacterForm } from "../components/character-form.js";
import { showAlert } from "../components/form.js";
import { CHARACTER_PAGE } from "../session.js";

const form = document.querySelector("#character-form");
const fieldset = document.querySelector("#character-fields");
const alertBox = document.querySelector("#character-alert");
const submitButton = form.querySelector('button[type="submit"]');
const emailText = document.querySelector("#account-email");

async function loadProfile() {
  try {
    const [profile, user] = await Promise.all([getProfile(), getCurrentUser()]);
    fillCharacterForm(form, profile);
    emailText.textContent = user.email;
    fieldset.disabled = false;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // No character yet, so there is nothing to edit
      window.location.replace(CHARACTER_PAGE);
      return;
    }
    emailText.textContent = "Could not be loaded.";
    showAlert(alertBox, "Your profile could not be loaded. Refresh the page to try again.");
    handleApiError(error);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = "Saving…";

  const profile = await saveCharacterForm(form, alertBox);
  if (profile) {
    fillCharacterForm(form, profile);
    showAlert(alertBox, "Your character was saved.", "success");
  }
  submitButton.disabled = false;
  submitButton.textContent = "Save changes";
});

loadProfile();

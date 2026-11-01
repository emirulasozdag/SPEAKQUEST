// Profile page: shows the saved character and account email, saves character changes, changes
// the password, resets the game progress and deletes the account.

import {
  ApiError,
  changePassword,
  deleteAccount,
  getCurrentUser,
  getProfile,
  handleApiError,
  resetProgress,
} from "../api.js";
import { fillCharacterForm, saveCharacterForm } from "../components/character-form.js";
import { clearErrorsOnEdit, setFieldError, showAlert } from "../components/form.js";
import { CHARACTER_PAGE } from "../session.js";
import { clearSession } from "../state.js";

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

const deleteForm = document.querySelector("#delete-account-form");
const deleteAlert = document.querySelector("#delete-account-alert");
const deletePassword = document.querySelector("#delete-password");
const deleteConfirm = document.querySelector("#delete-confirm");
const deleteButton = deleteForm.querySelector('button[type="submit"]');

deleteForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  deleteAlert.hidden = true;
  setFieldError(deletePassword, deletePassword.value ? null : "Enter your current password.");
  setFieldError(deleteConfirm, deleteConfirm.checked ? null : "Tick the box to confirm.");
  if (!deletePassword.value || !deleteConfirm.checked) return;

  deleteButton.disabled = true;
  deleteButton.textContent = "Deleting…";
  try {
    await deleteAccount(deletePassword.value);
    clearSession();
    window.location.assign("/");
    return;
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      setFieldError(deletePassword, error.message);
    } else if (error instanceof ApiError && error.status !== 401) {
      showAlert(deleteAlert, "Your account could not be deleted. Please try again.");
    } else {
      handleApiError(error);
    }
  }
  deleteButton.disabled = false;
  deleteButton.textContent = "Delete my account";
});

// ---------- Change password ----------

const passwordForm = document.querySelector("#password-form");
const passwordAlert = document.querySelector("#password-alert");
const currentPassword = document.querySelector("#current-password");
const newPassword = document.querySelector("#new-password");
const repeatPassword = document.querySelector("#repeat-password");
const passwordButton = passwordForm.querySelector('button[type="submit"]');

function closeDialog(element) {
  window.bootstrap.Modal.getOrCreateInstance(element.closest(".modal")).hide();
}

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  passwordAlert.hidden = true;
  setFieldError(currentPassword, currentPassword.value ? null : "Enter your current password.");
  setFieldError(newPassword, newPassword.value.length >= 8 ? null : "Use at least 8 characters.");
  setFieldError(repeatPassword, repeatPassword.value === newPassword.value ? null : "The two new passwords do not match.");
  if (passwordForm.querySelector(".is-invalid")) return;

  passwordButton.disabled = true;
  try {
    await changePassword(currentPassword.value, newPassword.value);
    passwordForm.reset();
    closeDialog(passwordForm);
    showAlert(alertBox, "Your password was changed.", "success");
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      setFieldError(currentPassword, error.message);
    } else if (error instanceof ApiError && error.status === 422) {
      setFieldError(newPassword, error.message);
    } else if (error instanceof ApiError && error.status !== 401) {
      showAlert(passwordAlert, "Your password could not be changed. Please try again.");
    } else {
      handleApiError(error);
    }
  }
  passwordButton.disabled = false;
});

// ---------- Reset game progress ----------

const resetForm = document.querySelector("#reset-form");
const resetAlert = document.querySelector("#reset-alert");
const resetConfirm = document.querySelector("#reset-confirm");
const resetButton = resetForm.querySelector('button[type="submit"]');

resetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetAlert.hidden = true;
  setFieldError(resetConfirm, resetConfirm.checked ? null : "Tick the box to confirm.");
  if (!resetConfirm.checked) return;

  resetButton.disabled = true;
  try {
    await resetProgress();
    resetForm.reset();
    closeDialog(resetForm);
    showAlert(alertBox, "Your game progress was reset. Your adventure starts again from the city map.", "success");
  } catch (error) {
    if (error instanceof ApiError && error.status !== 401) {
      showAlert(resetAlert, "Your progress could not be reset. Please try again.");
    } else {
      handleApiError(error);
    }
  }
  resetButton.disabled = false;
});

clearErrorsOnEdit(form);
clearErrorsOnEdit(deleteForm);
clearErrorsOnEdit(passwordForm);
clearErrorsOnEdit(resetForm);
loadProfile();

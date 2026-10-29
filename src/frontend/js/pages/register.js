// Register page: validates the form, creates the account through the API, logs the new player
// in and moves on to character creation.

import { ApiError, LOGIN_PAGE, handleApiError, registerUser } from "../api.js";
import { applyFieldErrors, clearErrorsOnEdit, setFieldError } from "../components/form.js";
import { CHARACTER_PAGE, logIn } from "../session.js";

const form = document.querySelector("#register-form");
const alertBox = document.querySelector("#register-alert");
const submitButton = form.querySelector('button[type="submit"]');
const fields = {
  email: form.querySelector("#register-email"),
  password: form.querySelector("#register-password"),
  confirm: form.querySelector("#register-password-confirm"),
};

clearErrorsOnEdit(form);

function validate() {
  const errors = {};
  if (!fields.email.value.trim() || !fields.email.validity.valid) {
    errors.email = "Enter a valid email address.";
  }
  if (fields.password.value.length < 8) {
    errors.password = "Use at least 8 characters.";
  }
  if (fields.confirm.value !== fields.password.value) {
    errors.confirm = "The passwords do not match.";
  }
  return errors;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  alertBox.hidden = true;

  const errors = validate();
  Object.entries(fields).forEach(([name, input]) => setFieldError(input, errors[name]));
  const firstInvalid = Object.keys(fields).find((name) => errors[name]);
  if (firstInvalid) {
    fields[firstInvalid].focus();
    return;
  }

  const email = fields.email.value.trim();
  const password = fields.password.value;
  submitButton.disabled = true;
  submitButton.textContent = "Creating account…";
  try {
    await registerUser(email, password);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      setFieldError(fields.email, "An account with this email already exists.");
      fields.email.focus();
    } else {
      handleApiError(error, { onFieldErrors: (fieldErrors) => applyFieldErrors(fields, fieldErrors) });
    }
    submitButton.disabled = false;
    submitButton.textContent = "Create account";
    return;
  }

  try {
    await logIn(email, password);
    window.location.assign(CHARACTER_PAGE);
  } catch {
    // The account exists even if the automatic login failed, so the player can log in by hand
    window.location.assign(LOGIN_PAGE);
  }
});

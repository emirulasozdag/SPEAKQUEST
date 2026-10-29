// Login page: checks the form, exchanges email and password for an access token and opens
// the dashboard, or character creation for players who have no character yet.

import { ApiError, handleApiError } from "../api.js";
import { applyFieldErrors, clearErrorsOnEdit, setFieldError, showAlert } from "../components/form.js";
import { logIn, pageAfterLogin } from "../session.js";

const form = document.querySelector("#login-form");
const alertBox = document.querySelector("#login-alert");
const submitButton = form.querySelector('button[type="submit"]');
const fields = {
  email: form.querySelector("#login-email"),
  password: form.querySelector("#login-password"),
};

clearErrorsOnEdit(form);

function validate() {
  const errors = {};
  if (!fields.email.value.trim() || !fields.email.validity.valid) {
    errors.email = "Enter a valid email address.";
  }
  if (!fields.password.value) {
    errors.password = "Enter your password.";
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

  submitButton.disabled = true;
  submitButton.textContent = "Logging in…";
  try {
    await logIn(fields.email.value.trim(), fields.password.value);
    window.location.assign(await pageAfterLogin());
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showAlert(alertBox, "Incorrect email or password.");
      fields.password.value = "";
      fields.password.focus();
    } else {
      handleApiError(error, { onFieldErrors: (fieldErrors) => applyFieldErrors(fields, fieldErrors) });
    }
    submitButton.disabled = false;
    submitButton.textContent = "Log in";
  }
});

// Register page: validates the form, creates the account through the API and moves on
// to character creation.

import { ApiError, registerUser } from "../api.js";
import { setSession } from "../state.js";

const form = document.querySelector("#register-form");
const alertBox = document.querySelector("#register-alert");
const submitButton = form.querySelector('button[type="submit"]');
const fields = {
  email: form.querySelector("#register-email"),
  password: form.querySelector("#register-password"),
  confirm: form.querySelector("#register-password-confirm"),
};

function showAlert(message, kind = "danger") {
  alertBox.className = `alert alert-${kind}`;
  alertBox.textContent = message;
  alertBox.hidden = false;
}

function setFieldError(input, message) {
  const feedback = form.querySelector(`#${input.id}-error`);
  input.classList.toggle("is-invalid", Boolean(message));
  input.setAttribute("aria-invalid", message ? "true" : "false");
  feedback.textContent = message ?? "";
}

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

  submitButton.disabled = true;
  submitButton.textContent = "Creating account…";
  try {
    const user = await registerUser(fields.email.value.trim(), fields.password.value);
    setSession({ email: user.email, userId: user.id });
    showAlert("Account created. Next, create your character.", "success");
    window.setTimeout(() => window.location.assign("/pages/character.html"), 1200);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      setFieldError(fields.email, "An account with this email already exists.");
      fields.email.focus();
    } else if (error instanceof ApiError && error.status === 422) {
      error.fieldErrors.forEach(({ loc, msg }) => {
        const input = fields[loc.at(-1)];
        if (input) setFieldError(input, msg);
      });
    } else {
      showAlert("The server could not be reached. Check that it is running and try again.");
    }
    submitButton.disabled = false;
    submitButton.textContent = "Create account";
  }
});

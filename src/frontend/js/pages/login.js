// Login page: checks the form, exchanges email and password for an access token
// and opens the dashboard.

import { ApiError, getCurrentUser, loginUser } from "../api.js";
import { setSession } from "../state.js";

const form = document.querySelector("#login-form");
const alertBox = document.querySelector("#login-alert");
const submitButton = form.querySelector('button[type="submit"]');
const fields = {
  email: form.querySelector("#login-email"),
  password: form.querySelector("#login-password"),
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
    const { access_token: token, expires_in: expiresIn } = await loginUser(
      fields.email.value.trim(),
      fields.password.value,
    );
    const user = await getCurrentUser(token);
    setSession({
      token,
      tokenExpiresAt: Date.now() + expiresIn * 1000,
      email: user.email,
      userId: user.id,
    });
    window.location.assign("/pages/dashboard.html");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      showAlert("Incorrect email or password.");
      fields.password.value = "";
      fields.password.focus();
    } else if (error instanceof ApiError && error.status === 422) {
      error.fieldErrors.forEach(({ loc, msg }) => {
        const input = fields[loc.at(-1)];
        if (input) setFieldError(input, msg);
      });
    } else {
      showAlert("The server could not be reached. Check that it is running and try again.");
    }
    submitButton.disabled = false;
    submitButton.textContent = "Log in";
  }
});

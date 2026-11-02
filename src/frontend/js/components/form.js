// Helpers for forms that show an alert above the form and errors next to each field.
// A field's error text goes into the element with id "<field id>-error".

export function showAlert(alertBox, message, kind = "danger") {
  alertBox.className = `alert alert-${kind}`;
  alertBox.textContent = message;
  alertBox.hidden = false;
  // The alert sits above the form, so on small screens it can be out of view after submitting
  alertBox.scrollIntoView({ block: "nearest" });
}

export function setFieldError(field, message) {
  const feedback = document.getElementById(`${field.id}-error`);
  field.classList.toggle("is-invalid", Boolean(message));
  field.setAttribute("aria-invalid", message ? "true" : "false");
  feedback.textContent = message ?? "";
  // d-block also shows the text for fields Bootstrap does not style, such as a fieldset
  feedback.classList.toggle("d-block", Boolean(message));
}

// Moves focus to the first field with an error so screen readers read its message.
// Returns true when there was one, so the caller can stop before submitting.
export function focusFirstInvalid(form) {
  const field = form.querySelector(".is-invalid");
  field?.focus();
  return Boolean(field);
}

// Hides a field's error as soon as the player changes that field, so an old message never
// sits next to a value that has already been fixed.
export function clearErrorsOnEdit(form) {
  form.addEventListener("input", (event) => {
    // closest() also finds a fieldset marked invalid, such as the avatar choice
    const field = event.target.closest(".is-invalid");
    if (field) setFieldError(field, null);
  });
}

// Shows validation errors from the API (422) next to the matching fields.
// fields maps API field names to elements; the API names the field in the last part of loc.
// Returns false when an error did not belong to any field, so the page can show it elsewhere.
export function applyFieldErrors(fields, fieldErrors) {
  let allShown = true;
  fieldErrors.forEach(({ loc, msg }) => {
    const field = fields[loc.at(-1)];
    if (field) {
      setFieldError(field, msg);
    } else {
      allShown = false;
    }
  });
  return allShown;
}

// The character form shared by character creation and the profile page.
// Both pages use the same field ids, so this module reads, fills, checks and saves them.

import { handleApiError, saveProfile } from "../api.js";
import { applyFieldErrors, setFieldError, showAlert } from "./form.js";

const NAME_MAX_LENGTH = 30;

function characterFields(form) {
  return {
    character_name: form.querySelector("#character-name"),
    avatar: form.querySelector("#avatar"),
    english_level: form.querySelector("#english-level"),
    learning_goal: form.querySelector("#learning-goal"),
  };
}

function readCharacter(form) {
  const data = new FormData(form);
  return {
    character_name: data.get("character_name").trim(),
    avatar: Number(data.get("avatar")),
    english_level: data.get("english_level"),
    learning_goal: data.get("learning_goal"),
  };
}

function validateCharacter(character) {
  const errors = {};
  if (!character.character_name) {
    errors.character_name = "Give your character a name.";
  } else if (character.character_name.length > NAME_MAX_LENGTH) {
    errors.character_name = `Use at most ${NAME_MAX_LENGTH} characters.`;
  }
  return errors;
}

export function fillCharacterForm(form, profile) {
  form.querySelector("#character-name").value = profile.character_name;
  form.querySelector(`#avatar-${profile.avatar}`).checked = true;
  form.querySelector("#english-level").value = profile.english_level;
  form.querySelector("#learning-goal").value = profile.learning_goal;
}

// Checks and saves the form. Returns the saved profile, or null when the player has to fix
// something first; the problems are already shown next to the fields or in alertBox.
export async function saveCharacterForm(form, alertBox) {
  const fields = characterFields(form);
  const character = readCharacter(form);
  alertBox.hidden = true;

  const errors = validateCharacter(character);
  Object.entries(fields).forEach(([name, field]) => setFieldError(field, errors[name]));
  if (errors.character_name) {
    fields.character_name.focus();
    return null;
  }

  try {
    return await saveProfile(character);
  } catch (error) {
    handleApiError(error, {
      onFieldErrors: (fieldErrors) => {
        if (!applyFieldErrors(fields, fieldErrors)) {
          showAlert(alertBox, "Some details could not be saved. Check the form and try again.");
        }
      },
    });
    return null;
  }
}

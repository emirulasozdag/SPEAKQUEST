// Shared wording and links for quests, so the dashboard and the map describe them the same way.

export const QUEST_STATUS_LABELS = {
  locked: "Locked",
  available: "Available",
  active: "In progress",
  completed: "Completed",
};

export function dialogueUrl(questId) {
  return `/pages/dialogue.html?quest=${encodeURIComponent(questId)}`;
}

export function avatarUrl(avatar) {
  return `/assets/avatars/avatar-${avatar}.svg`;
}

export function portraitUrl(npcSlug) {
  return `/assets/portraits/${npcSlug}.svg`;
}

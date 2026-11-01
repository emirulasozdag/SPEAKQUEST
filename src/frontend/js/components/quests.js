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

export const MAP_PAGE = "/pages/map.html";
export const JOURNAL_PAGE = "/pages/journal.html";
export const ENDING_PAGE = "/pages/ending.html";

// Heading above the Adaptive Quest Engine's reason, the same on the dashboard and in the journal
export const RECOMMENDATION_HEADING = "Why this quest was suggested for you";

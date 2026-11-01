// Names for the five skill categories and their states, shared by the progress page.

export const SKILLS = [
  { id: "present_simple", label: "Present Simple" },
  { id: "past_simple", label: "Past Simple" },
  { id: "question_formation", label: "Question Formation" },
  { id: "prepositions", label: "Prepositions" },
  { id: "vocabulary_usage", label: "Vocabulary Usage" },
];

export const STATUS_LABELS = {
  not_practised: "Not practised yet",
  weak: "Needs practice",
  developing: "Getting there",
  strong: "Strong",
};

export function skillLabel(category) {
  return SKILLS.find((skill) => skill.id === category)?.label ?? category;
}

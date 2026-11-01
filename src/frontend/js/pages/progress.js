// Learning Progress page: skill scores, the mistakes the player makes most and a chart of the
// skills over time. Every number comes from the Learning Engine through the API.

import {
  ApiError,
  getLearningErrors,
  getLearningTimeline,
  getRecommendations,
  getSkills,
  handleApiError,
} from "../api.js";
import { showAlert } from "../components/form.js";
import { SKILLS, STATUS_LABELS, skillLabel } from "../components/skills.js";

const SVG_NS = "http://www.w3.org/2000/svg";
// Examples shown per skill in the mistakes list
const EXAMPLES_PER_SKILL = 2;

const loading = document.querySelector("#progress-loading");
const alertBox = document.querySelector("#progress-alert");
const emptyBox = document.querySelector("#progress-empty");
const content = document.querySelector("#progress-content");

// ---------- Skills ----------

function skillItem(skill) {
  const item = document.createElement("li");
  item.className = "sq-skill-row";
  item.dataset.status = skill.status;
  const practised = skill.opportunities > 0;
  item.innerHTML = `
    <div class="d-flex justify-content-between align-items-baseline gap-2 mb-1">
      <span class="fw-bold skill-name"></span>
      <span class="skill-score"></span>
    </div>
    <div class="progress sq-skill-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100">
      <div class="progress-bar"></div>
    </div>
    <p class="small text-secondary mb-0 mt-1 skill-detail"></p>`;
  item.querySelector(".skill-name").textContent = skillLabel(skill.category);
  item.querySelector(".skill-score").textContent = practised ? `${skill.score} / 100` : "–";
  const bar = item.querySelector(".progress");
  bar.setAttribute("aria-label", `${skillLabel(skill.category)} score`);
  bar.setAttribute("aria-valuenow", String(practised ? skill.score : 0));
  bar.setAttribute("aria-valuetext", practised ? `${skill.score} of 100, ${STATUS_LABELS[skill.status]}` : "Not practised yet");
  bar.firstElementChild.style.width = `${practised ? skill.score : 0}%`;

  const parts = [STATUS_LABELS[skill.status] ?? skill.status];
  if (practised) {
    parts.push(`${skill.correct_count} correct, ${skill.error_count} ${skill.error_count === 1 ? "mistake" : "mistakes"}`);
  }
  if (skill.repeated) parts.push("a mistake you keep making");
  item.querySelector(".skill-detail").textContent = parts.join(" · ");
  return item;
}

function showSkills(skills) {
  const byCategory = new Map(skills.map((skill) => [skill.category, skill]));
  const list = document.querySelector("#skill-list");
  list.replaceChildren(...SKILLS.map(({ id }) => byCategory.get(id)).filter(Boolean).map(skillItem));
}

function showTarget(target) {
  const panel = document.querySelector("#target-panel");
  panel.innerHTML = '<p class="small mb-1">Practise next</p><p class="fw-bold mb-1"></p><p class="small mb-0"></p>';
  panel.querySelector(".fw-bold").textContent = skillLabel(target.category);
  panel.querySelector("p.mb-0").textContent = target.message;
  panel.hidden = false;
}

// ---------- Mistakes ----------

function showMistakes(errors, skills) {
  const list = document.querySelector("#mistake-list");
  const groups = new Map();
  for (const error of errors) {
    if (!groups.has(error.category)) groups.set(error.category, []);
    groups.get(error.category).push(error);
  }
  // Most mistakes first; the count is the Learning Engine's total, not only this page of errors
  const totals = new Map(skills.map((skill) => [skill.category, skill.error_count]));
  const ordered = [...groups.keys()].sort((a, b) => (totals.get(b) ?? 0) - (totals.get(a) ?? 0));

  if (!ordered.length) {
    list.innerHTML = '<li class="text-secondary">No mistakes yet. Keep talking and they will show up here with their corrections.</li>';
    return;
  }
  for (const category of ordered) {
    const item = document.createElement("li");
    item.className = "sq-skill-row";
    const heading = document.createElement("p");
    heading.className = "fw-bold mb-1";
    const count = totals.get(category) ?? groups.get(category).length;
    heading.textContent = `${skillLabel(category)} · ${count} ${count === 1 ? "time" : "times"}`;
    item.append(heading);
    for (const error of groups.get(category).slice(0, EXAMPLES_PER_SKILL)) {
      const example = document.createElement("p");
      example.className = "mb-1";
      example.innerHTML = '<span class="sq-wrong"></span> → <span class="sq-right"></span>';
      example.querySelector(".sq-wrong").textContent = error.original;
      example.querySelector(".sq-right").textContent = error.corrected;
      const note = document.createElement("p");
      note.className = "small text-secondary mb-2";
      note.textContent = [error.explanation, error.quest_title].filter(Boolean).join(" · ");
      item.append(example, note);
    }
    list.append(item);
  }
}

// ---------- Chart (plain SVG) ----------

function svg(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function dayLabel(day) {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });
}

// The same numbers as a table, for screen readers and as a fallback
function chartTable(points) {
  // The wrapper is hidden, not the table: a table ignores the 1px size and would widen the page
  const wrapper = document.createElement("div");
  wrapper.className = "visually-hidden";
  const table = document.createElement("table");
  wrapper.append(table);
  const caption = table.createCaption();
  caption.textContent = "Skill scores at the end of each day you practised";
  const head = table.createTHead().insertRow();
  ["Day", ...SKILLS.map((skill) => skill.label)].forEach((text) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = text;
    head.append(cell);
  });
  const body = table.createTBody();
  for (const point of points) {
    const row = body.insertRow();
    const day = document.createElement("th");
    day.scope = "row";
    day.textContent = dayLabel(point.day);
    row.append(day);
    const scores = new Map(point.scores.map((item) => [item.category, item.score]));
    for (const skill of SKILLS) row.insertCell().textContent = scores.get(skill.id) ?? "–";
  }
  return wrapper;
}

function showChart(points) {
  const host = document.querySelector("#chart");
  const legend = document.querySelector("#chart-legend");
  if (points.length < 2) {
    host.innerHTML = '<p class="text-secondary mb-0">Practise on at least two different days to see how your skills change over time.</p>';
    legend.hidden = true;
    if (points.length) host.append(chartTable(points));
    return;
  }

  // Drawn at the container's real width, so labels keep their size on a phone
  const width = Math.max(300, Math.round(host.clientWidth) || 720);
  const height = width < 500 ? 220 : 280;
  const pad = { top: 16, right: 16, bottom: 36, left: 40 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const x = (index) => pad.left + (plotWidth * index) / (points.length - 1);
  const y = (score) => pad.top + plotHeight * (1 - score / 100);

  const chart = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "sq-chart", "aria-hidden": "true" });
  for (const score of [0, 50, 75, 100]) {
    chart.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: y(score), y2: y(score), class: "sq-chart-grid" }));
    const label = svg("text", { x: pad.left - 8, y: y(score) + 4, "text-anchor": "end", class: "sq-chart-label" });
    label.textContent = score;
    chart.append(label);
  }
  // At most about six day labels, always including the first and the last day
  const step = Math.max(1, Math.ceil(points.length / (width < 500 ? 3 : 6)));
  points.forEach((point, index) => {
    if (index % step && index !== points.length - 1) return;
    // The first and last labels sit inside the edges instead of being centred on them
    const anchor = index === 0 ? "start" : index === points.length - 1 ? "end" : "middle";
    const label = svg("text", { x: x(index), y: height - 12, "text-anchor": anchor, class: "sq-chart-label" });
    label.textContent = dayLabel(point.day);
    chart.append(label);
  });

  legend.replaceChildren();
  SKILLS.forEach((skill, number) => {
    const series = points
      .map((point, index) => ({ index, score: point.scores.find((item) => item.category === skill.id)?.score }))
      .filter((item) => item.score !== null && item.score !== undefined);
    if (!series.length) return;
    const className = `sq-chart-series sq-series-${number + 1}`;
    chart.append(svg("polyline", { points: series.map((item) => `${x(item.index)},${y(item.score)}`).join(" "), class: className }));
    for (const item of series) chart.append(svg("circle", { cx: x(item.index), cy: y(item.score), r: 4, class: className }));

    const entry = document.createElement("li");
    entry.innerHTML = `<span class="sq-legend-swatch sq-series-${number + 1}" aria-hidden="true"></span>`;
    entry.append(`${skill.label}: ${series.at(-1).score}`);
    legend.append(entry);
  });
  legend.hidden = false;
  host.replaceChildren(chart, chartTable(points));
}

// ---------- Load ----------

async function loadProgress() {
  try {
    const [skills, errors, timeline] = await Promise.all([getSkills(), getLearningErrors(), getLearningTimeline()]);
    if (!skills.skills.some((skill) => skill.opportunities > 0)) {
      emptyBox.hidden = false;
      return;
    }
    showSkills(skills.skills);
    showMistakes(errors.errors, skills.skills);
    content.hidden = false;
    showChart(timeline.points);
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => showChart(timeline.points), 150);
    });
    try {
      showTarget((await getRecommendations()).target);
    } catch (error) {
      // The target needs a character; the rest of the page does not
      if (!(error instanceof ApiError && error.status === 404)) handleApiError(error);
    }
  } catch (error) {
    showAlert(alertBox, "Your progress could not be loaded. Refresh the page to try again.");
    handleApiError(error);
  } finally {
    loading.hidden = true;
  }
}

loadProgress();

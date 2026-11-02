// Unit tests for the voice component (#28). Run with: node --test src/frontend/tests/
// They use small fakes for the browser APIs, so no browser or microphone is needed.

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_SETTINGS,
  MAX_RATE,
  MIN_RATE,
  SETTINGS_KEY,
  clampRate,
  createDictation,
  createSpeaker,
  describeRecognitionError,
  englishVoices,
  joinTranscript,
  parseSettings,
  pickVoice,
  recognitionClass,
} from "../js/components/voice.js";

// ---------- joinTranscript ----------

test("spoken words go into an empty box as they are", () => {
  assert.equal(joinTranscript("", "  hello there "), "hello there");
});

test("spoken words are added after what is already typed, with one space", () => {
  assert.equal(joinTranscript("I worked", "in a restaurant"), "I worked in a restaurant");
  assert.equal(joinTranscript("I worked   ", "in a  restaurant"), "I worked in a restaurant");
});

test("silence changes nothing", () => {
  assert.equal(joinTranscript("Typed text ", "   "), "Typed text ");
});

test("the result never goes over the message limit", () => {
  const result = joinTranscript("a".repeat(495), "bbbbbbbbbb", 500);
  assert.equal(result.length, 500);
  assert.ok(result.startsWith("a".repeat(495) + " "));
});

// ---------- errors ----------

test("a blocked microphone gets a clear, helpful message", () => {
  const message = describeRecognitionError("not-allowed");
  assert.match(message, /Microphone access was blocked/);
  assert.match(message, /type your answer/);
});

test("an unknown error still gets a message", () => {
  assert.match(describeRecognitionError("something-new"), /type your answer/);
});

// ---------- settings ----------

test("read-aloud is off by default", () => {
  assert.equal(DEFAULT_SETTINGS.autoRead, false);
  assert.deepEqual(parseSettings(null), { ...DEFAULT_SETTINGS });
});

test("broken or strange stored settings fall back safely", () => {
  assert.deepEqual(parseSettings("{not json"), { ...DEFAULT_SETTINGS });
  assert.deepEqual(parseSettings('"text"'), { ...DEFAULT_SETTINGS });
  assert.deepEqual(parseSettings('{"autoRead":"yes","voiceURI":5,"rate":"fast"}'), { ...DEFAULT_SETTINGS });
});

test("valid stored settings are kept", () => {
  assert.deepEqual(parseSettings('{"autoRead":true,"voiceURI":"v1","rate":1.2}'), {
    autoRead: true,
    voiceURI: "v1",
    rate: 1.2,
  });
});

test("the speed stays within its limits", () => {
  assert.equal(clampRate(5), MAX_RATE);
  assert.equal(clampRate(0.1), MIN_RATE);
  assert.equal(clampRate(1.1), 1.1);
  assert.equal(clampRate(Number.NaN), DEFAULT_SETTINGS.rate);
});

// ---------- voices ----------

const voice = (name, lang, localService = true) => ({ name, lang, localService, voiceURI: `${name}-${lang}` });
const VOICES = [voice("Anna", "de-DE"), voice("Remote US", "en-US", false), voice("Kate", "en-GB"), voice("Ali", "tr-TR")];

test("only English voices are offered", () => {
  assert.deepEqual(englishVoices(VOICES).map((item) => item.name), ["Remote US", "Kate"]);
});

test("the saved voice is used when it still exists", () => {
  assert.equal(pickVoice(VOICES, "Remote US-en-US").name, "Remote US");
});

test("otherwise a local British voice is preferred, then American", () => {
  assert.equal(pickVoice(VOICES, "gone").name, "Kate");
  assert.equal(pickVoice([voice("Remote US", "en-US", false), voice("Local US", "en_US")]).name, "Local US");
});

test("no English voice means no choice", () => {
  assert.equal(pickVoice([voice("Ali", "tr-TR")]), null);
});

// ---------- read-aloud with a fake browser ----------

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      data[key] = String(value);
    },
    data,
  };
}

function fakeSpeechScope(storage = fakeStorage()) {
  const spoken = [];
  let cancelled = 0;
  return {
    localStorage: storage,
    SpeechSynthesisUtterance: class {
      constructor(text) {
        this.text = text;
      }
    },
    speechSynthesis: {
      getVoices: () => VOICES,
      speak: (utterance) => spoken.push(utterance),
      cancel: () => {
        cancelled += 1;
      },
    },
    spoken,
    get cancelled() {
      return cancelled;
    },
  };
}

test("speaking uses an English voice and the chosen speed, and replaces the line being read", () => {
  const scope = fakeSpeechScope(fakeStorage({ [SETTINGS_KEY]: '{"rate":0.8}' }));
  const speaker = createSpeaker(scope);

  assert.equal(speaker.speak("Good morning!"), true);

  const [utterance] = scope.spoken;
  assert.equal(utterance.text, "Good morning!");
  assert.equal(utterance.voice.name, "Kate");
  assert.equal(utterance.rate, 0.8);
  assert.equal(scope.cancelled, 1);
});

test("settings changes are clamped and remembered in this browser", () => {
  const storage = fakeStorage();
  const speaker = createSpeaker(fakeSpeechScope(storage));

  speaker.update({ autoRead: true, rate: 9 });

  assert.deepEqual(JSON.parse(storage.data[SETTINGS_KEY]), { autoRead: true, voiceURI: null, rate: MAX_RATE });
});

test("without speech synthesis nothing is spoken and nothing breaks", () => {
  const speaker = createSpeaker({ localStorage: fakeStorage() });

  assert.equal(speaker.supported, false);
  assert.equal(speaker.speak("Hello"), false);
  assert.deepEqual(speaker.voices(), []);
  speaker.stop();
});

// ---------- dictation with a fake browser ----------

function fakeElement(extra = {}) {
  const listeners = {};
  return {
    hidden: true,
    textContent: "",
    value: "",
    maxLength: 500,
    attributes: {},
    classes: new Set(),
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
    classList: {
      toggle(name, on) {
        this.owner.classes[on ? "add" : "delete"](name);
      },
    },
    addEventListener: (type, handler) => {
      listeners[type] = handler;
    },
    click: () => listeners.click?.(),
    focus() {},
    querySelector() {
      return this.label;
    },
    ...extra,
  };
}

function dictationParts(scope) {
  const button = fakeElement({ label: { textContent: "Speak" } });
  button.classList.owner = button;
  const input = fakeElement();
  const status = fakeElement();
  let changes = 0;
  const dictation = createDictation({ button, input, status, onChange: () => (changes += 1), scope });
  return { button, input, status, dictation, changes: () => changes };
}

function recognitionScope() {
  const instances = [];
  class FakeRecognition {
    constructor() {
      instances.push(this);
    }
    start() {
      this.started = true;
      this.onstart?.();
    }
    stop() {
      this.onend?.();
    }
  }
  return { webkitSpeechRecognition: FakeRecognition, instances };
}

function results(...items) {
  return {
    resultIndex: 0,
    results: items.map(([transcript, isFinal]) => Object.assign([{ transcript }], { isFinal })),
  };
}

test("the microphone button stays hidden where speech recognition is missing", () => {
  const { button, dictation } = dictationParts({});

  assert.equal(button.hidden, true);
  assert.equal(dictation.supported, false);
  assert.equal(recognitionClass({}), null);
});

test("speech goes into the box for editing and is never sent on its own", () => {
  const scope = recognitionScope();
  const { button, input, status, changes } = dictationParts(scope);
  input.value = "Hello,";

  button.click();
  const [recognition] = scope.instances;
  assert.equal(recognition.lang, "en-US");
  assert.equal(button.attributes["aria-pressed"], "true");
  assert.equal(button.label.textContent, "Stop");

  recognition.onresult(results(["I worked in a", false]));
  assert.equal(input.value, "Hello,");
  assert.match(status.textContent, /Heard: I worked in a/);

  recognition.onresult(results(["I worked in a restaurant", true]));
  recognition.onend();

  assert.equal(input.value, "Hello, I worked in a restaurant");
  assert.equal(changes(), 1);
  assert.equal(button.attributes["aria-pressed"], "false");
  assert.match(status.textContent, /Check the text/);
});

test("a blocked microphone shows the message and keeps the typed text", () => {
  const scope = recognitionScope();
  const { button, input, status } = dictationParts(scope);
  input.value = "Typed";

  button.click();
  const [recognition] = scope.instances;
  recognition.onerror({ error: "not-allowed" });
  recognition.onend();

  assert.match(status.textContent, /Microphone access was blocked/);
  assert.equal(status.hidden, false);
  assert.equal(input.value, "Typed");
});

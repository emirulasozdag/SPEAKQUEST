// Voice input and read-aloud for the dialogue screen (#28), built on the browser's Web Speech API.
//
// - Dictation turns speech into text in the message box. It is never sent on its own: the player
//   reads and edits it first. SpeakQuest's server never receives or stores audio; the browser's
//   speech service turns it into text (see the privacy page).
// - Read-aloud speaks NPC lines with speechSynthesis. It is off by default; each line also has
//   its own "Listen" button.
// Everything that touches the browser is created on demand, so the pure helpers below can be
// tested in Node (src/frontend/tests/voice.test.mjs).

export const SETTINGS_KEY = "speakquest.voice";
export const DEFAULT_SETTINGS = Object.freeze({ autoRead: false, voiceURI: null, rate: 1 });
export const MIN_RATE = 0.7;
export const MAX_RATE = 1.3;
export const RECOGNITION_LANG = "en-US";

// What the player sees for each SpeechRecognition error code
const ERROR_MESSAGES = {
  "not-allowed": "Microphone access was blocked. Allow the microphone for this site in your browser settings, or type your answer instead.",
  "service-not-allowed": "Speech recognition is turned off in this browser. You can still type your answer.",
  "no-speech": "No speech was heard. Press the microphone and try again.",
  "audio-capture": "No microphone was found. Check that one is connected, or type your answer.",
  network: "Speech recognition needs an internet connection. You can still type your answer.",
  aborted: "Listening stopped.",
  "language-not-supported": "This browser cannot recognise English speech. You can still type your answer.",
};

// ---------- Pure helpers ----------

/** The message box text after adding spoken words: one space between, never over maxLength. */
export function joinTranscript(existing, spoken, maxLength = 500) {
  const before = existing.replace(/\s+$/, "");
  const words = spoken.trim().replace(/\s+/g, " ");
  if (!words) return existing;
  const joined = before ? `${before} ${words}` : words;
  return joined.length > maxLength ? joined.slice(0, maxLength) : joined;
}

/** A player-facing sentence for a recognition error code. */
export function describeRecognitionError(code) {
  return ERROR_MESSAGES[code] ?? "Speech recognition did not work this time. You can still type your answer.";
}

export function clampRate(rate) {
  const value = Number(rate);
  if (!Number.isFinite(value)) return DEFAULT_SETTINGS.rate;
  return Math.min(MAX_RATE, Math.max(MIN_RATE, value));
}

/** Only English voices make sense for an English learning game. */
export function englishVoices(voices) {
  return voices.filter((voice) => /^en([-_]|$)/i.test(voice.lang));
}

/**
 * The voice to use: the saved one if it still exists, otherwise a local British or American
 * English voice, otherwise any English voice. Null when the browser has none.
 */
export function pickVoice(voices, savedURI = null) {
  const english = englishVoices(voices);
  if (!english.length) return null;
  const saved = english.find((voice) => voice.voiceURI === savedURI);
  if (saved) return saved;
  const preferred = ["en-GB", "en-US"];
  for (const lang of preferred) {
    const match = english.find((voice) => voice.lang.replace("_", "-") === lang && voice.localService)
      ?? english.find((voice) => voice.lang.replace("_", "-") === lang);
    if (match) return match;
  }
  return english[0];
}

/** Settings read from storage, with every value checked; a broken entry gives the defaults. */
export function parseSettings(raw) {
  try {
    const value = JSON.parse(raw ?? "null");
    if (!value || typeof value !== "object") return { ...DEFAULT_SETTINGS };
    return {
      autoRead: value.autoRead === true,
      voiceURI: typeof value.voiceURI === "string" ? value.voiceURI : null,
      rate: clampRate(value.rate ?? DEFAULT_SETTINGS.rate),
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

// ---------- Browser support ----------

export function recognitionClass(scope = globalThis) {
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function synthesisAvailable(scope = globalThis) {
  return Boolean(scope.speechSynthesis && scope.SpeechSynthesisUtterance);
}

// ---------- Settings ----------

export function loadSettings(storage = globalThis.localStorage) {
  try {
    return parseSettings(storage?.getItem(SETTINGS_KEY));
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(settings, storage = globalThis.localStorage) {
  try {
    storage?.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Private mode or full storage: the setting simply lasts for this page only
  }
}

// ---------- Read-aloud ----------

/** Speaks text with the player's chosen voice and speed. Does nothing where unsupported. */
export function createSpeaker(scope = globalThis) {
  const supported = synthesisAvailable(scope);
  let settings = loadSettings(scope.localStorage);

  function voices() {
    return supported ? scope.speechSynthesis.getVoices() : [];
  }

  return {
    supported,
    get settings() {
      return settings;
    },
    update(changes) {
      settings = { ...settings, ...changes, rate: clampRate(changes.rate ?? settings.rate) };
      saveSettings(settings, scope.localStorage);
      return settings;
    },
    voices: () => englishVoices(voices()),
    speak(text) {
      if (!supported || !text) return false;
      const utterance = new scope.SpeechSynthesisUtterance(text);
      const voice = pickVoice(voices(), settings.voiceURI);
      if (voice) utterance.voice = voice;
      utterance.lang = voice?.lang ?? "en-GB";
      utterance.rate = settings.rate;
      // A new line replaces the one still being read
      scope.speechSynthesis.cancel();
      scope.speechSynthesis.speak(utterance);
      return true;
    },
    stop() {
      if (supported) scope.speechSynthesis.cancel();
    },
  };
}

// ---------- Dictation ----------

/**
 * Wires a microphone button to the message box. The button is hidden where the browser has no
 * speech recognition. Spoken text is added to the box when the player stops; while they speak,
 * the status line shows what was heard so far.
 */
export function createDictation({ button, input, status, onChange, scope = globalThis }) {
  const Recognition = recognitionClass(scope);
  if (!Recognition) {
    button.hidden = true;
    return { supported: false, stop() {} };
  }

  let recognition = null;
  let listening = false;

  function setListening(value) {
    listening = value;
    button.setAttribute("aria-pressed", String(value));
    button.classList.toggle("is-listening", value);
    button.querySelector("[data-voice-label]").textContent = value ? "Stop" : "Speak";
  }

  function showStatus(text) {
    status.textContent = text;
    status.hidden = !text;
  }

  function start() {
    recognition = new Recognition();
    recognition.lang = RECOGNITION_LANG;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setListening(true);
      showStatus("Listening… speak in English, then press Stop or pause.");
    };
    recognition.onresult = (event) => {
      let finalText = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) finalText += result[0].transcript;
        else interim += result[0].transcript;
      }
      if (finalText) {
        input.value = joinTranscript(input.value, finalText, input.maxLength > 0 ? input.maxLength : 500);
        onChange?.();
      }
      showStatus(interim ? `Heard: ${interim}` : "Listening…");
    };
    recognition.onerror = (event) => {
      showStatus(describeRecognitionError(event.error));
    };
    recognition.onend = () => {
      setListening(false);
      if (status.textContent.startsWith("Listening") || status.textContent.startsWith("Heard")) {
        showStatus("Check the text, change anything you like, then send it.");
      }
      input.focus();
    };

    try {
      recognition.start();
    } catch {
      showStatus(describeRecognitionError("unknown"));
    }
  }

  function stop() {
    if (recognition && listening) recognition.stop();
  }

  button.hidden = false;
  button.addEventListener("click", () => (listening ? stop() : start()));
  return { supported: true, stop };
}

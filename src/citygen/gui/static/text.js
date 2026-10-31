// The page's words, in one language at a time. Every word the app shows is in i18n/<code>.json; Python answers with
// facts and short codes (gui/bridge.py), and this is where they become text.
//
// index.html and the code that builds elements name their words by key, in data-text (the element's text),
// data-text-title, data-text-placeholder and data-text-label (its aria-label). translate() fills them in, and again
// when the language changes.

"use strict";

// Every language, in its own name. Each has a file in i18n/, with the same keys and the same {placeholders}.
const LANGUAGES = {
  en: "English",
  de: "Deutsch",
  es: "Español",
  fr: "Français",
  pt: "Português",
  ru: "Русский",
  zh: "简体中文",
  ja: "日本語",
};

let TEXT = null;   // the current language's file

/** The first of the system's languages the app has, by its base code (``pt-PT`` is ``pt``), else English. */
function systemLanguage(tags = navigator.languages) {
  return tags.map((tag) => tag.split("-")[0].toLowerCase()).find((code) => code in LANGUAGES) ?? "en";
}

/** Switch the page to language ``code``. */
async function useLanguage(code) {
  TEXT = await (await fetch(`i18n/${code}.json`)).json();
  document.documentElement.lang = code;   // chooses the fonts (tokens.css) and how text breaks
  translate();
}

/** The words at ``key``, a dotted path into the language's file. */
function word(key) {
  return key.split(".").reduce((words, part) => words[part], TEXT);
}

/** ``template`` with each ``{name}`` replaced by ``values.name``. */
function fill(template, values) {
  return template.replace(/\{(\w+)\}/g, (_match, name) => values[name]);
}

/** Fill in the words of everything under ``root`` that names them. */
function translate(root = document) {
  for (const element of root.querySelectorAll("[data-text]")) element.textContent = word(element.dataset.text);
  for (const element of root.querySelectorAll("[data-text-title]")) element.title = word(element.dataset.textTitle);
  for (const element of root.querySelectorAll("[data-text-placeholder]")) {
    element.placeholder = word(element.dataset.textPlaceholder);
  }
  for (const element of root.querySelectorAll("[data-text-label]")) {
    element.setAttribute("aria-label", word(element.dataset.textLabel));
  }
}

/** ``{code, detail}`` from Python, on tab ``tab``, as ``{title, message}`` for the error dialog. */
function describeError({ code, detail }, tab) {
  if (code === "running") return TEXT.tabs[tab].running;
  if (code === "invalid_config") {   // ``detail`` is the knob's name
    const name = TEXT.form.knobs[detail]?.label ?? detail;
    return { title: TEXT.tabs[tab].invalidConfig, message: fill(TEXT.errors.invalid_config, { name }) };
  }
  const words = TEXT.errors[code];
  if (!words) return { title: TEXT.errors.unknown, message: detail || code };
  return { title: words.title, message: fill(words.message ?? "{detail}", { detail }) };
}

/** A run's failure, as ``{title, message}``: the tab's own title, and the failure's words, its error's text if it has
 *  none, or the title again. */
function describeFailure(tab, { code, detail }) {
  const title = TEXT.tabs[tab].failed;
  return { title, message: TEXT.failures[code] ?? (detail || title) };
}

// What every part of the page uses: ``$`` and ``$$`` to find elements, and the error dialog.

"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Show the error dialog. */
function showError({ title, message }) {
  const dialog = $("#error-dialog");
  $("h2", dialog).textContent = title;
  $("p", dialog).textContent = message;
  dialog.showModal();
}

// Entry point: connects the page's controls to the player and renderer.

import { createPlayer, delayForSpeed } from "./player.js";
import { createRenderer } from "./render.js";
import { createRpcClient } from "./transport.js";

const $ = (id) => document.getElementById(id);
const speed = $("speed");
const speedValue = $("speed-value");
const size = $("size");
const pauseAtSolution = $("pause-at-solution");

const renderer = createRenderer(document);
const player = createPlayer({
  rpc: createRpcClient((url, options) => fetch(url, options)),
  onChange: (state) => renderer.render(state),
  size: Number(size.value),
  delay: delayForSpeed(Number(speed.value)),
});

function showSpeed() {
  const delay = delayForSpeed(Number(speed.value));
  speedValue.textContent = `${delay} ms per event`;
  player.setDelay(delay);
}

$("start").addEventListener("click", () => player.start());
$("step").addEventListener("click", () => player.step());
$("play").addEventListener("click", () => player.togglePlay());
$("next-solution").addEventListener("click", () => player.nextSolution());
$("reset").addEventListener("click", () => player.reset());
speed.addEventListener("input", showSpeed);
size.addEventListener("change", () => player.setSize(Number(size.value)));
pauseAtSolution.addEventListener("change", () => player.setPauseAtSolution(pauseAtSolution.checked));

// Single-letter shortcuts, ignored while typing in a form control.
const shortcuts = { s: "step", p: "play", n: "next-solution", r: "reset" };
document.addEventListener("keydown", (event) => {
  if (event.altKey || event.ctrlKey || event.metaKey || event.target.closest("input, select, textarea")) return;
  const button = $(shortcuts[event.key.toLowerCase()] ?? "");
  if (button && !button.disabled) {
    event.preventDefault();
    button.click();
  }
});

player.setPauseAtSolution(pauseAtSolution.checked);
showSpeed();
renderer.render(player.state);
// Close the stream when the page goes away, so the server can release it.
window.addEventListener("pagehide", () => player.reset());

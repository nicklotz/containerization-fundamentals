// Baggage claim board.
// Every 3 seconds it reads /api/bags and /api/info from the web server that
// served this page. nginx forwards those requests to bag-api.
"use strict";

const POLL_MS = 3000;
const TIMEOUT_MS = 2500;
const MAX_ROWS = 25;

const page = {
  hub: document.getElementById("hub"),
  updated: document.getElementById("updated"),
  banner: document.getElementById("banner"),
  rows: document.getElementById("rows"),
  empty: document.getElementById("empty"),
  footer: document.getElementById("footer"),
};

// Fetch one API path and return the parsed JSON. Throws on errors and non-2xx answers.
async function getJSON(path) {
  const response = await fetch(path, { cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`${path} answered HTTP ${response.status}`);
  }
  return response.json();
}

// Turn a failed fetch into a short message for the banner.
function describe(error) {
  if (error.name === "TimeoutError") return `no answer within ${TIMEOUT_MS / 1000} seconds`;
  if (error instanceof TypeError) return "network error"; // fetch could not connect at all
  return error.message;
}

function cell(text, className) {
  const td = document.createElement("td");
  td.textContent = text; // textContent, not innerHTML: passenger names come from users
  if (className) td.className = className;
  return td;
}

function showBags(bags) {
  const rows = bags.slice(0, MAX_ROWS).map((bag) => {
    const tr = document.createElement("tr");
    tr.append(
      cell(bag.tag, "tag"),
      cell(bag.flight),
      cell(bag.destination),
      cell(bag.passenger),
      cell(bag.status.replace("_", " "), `status status-${bag.status}`),
    );
    return tr;
  });
  page.rows.replaceChildren(...rows);
  page.empty.hidden = rows.length > 0;
}

function showInfo(info) {
  page.hub.textContent = info.hub;
  document.title = `Baggage claim — ${info.hub}`;
  page.footer.textContent =
    `Served by bag-api ${info.hostname} · version ${info.version} · storage ${info.storage}`;
}

async function refresh() {
  const [bags, info] = await Promise.allSettled([
    getJSON(`/api/bags?limit=${MAX_ROWS}`),
    getJSON("/api/info"),
  ]);
  if (bags.status === "fulfilled") showBags(bags.value);
  if (info.status === "fulfilled") showInfo(info.value);

  const failure = [bags, info].find((result) => result.status === "rejected");
  // Keep the last table on screen, but dim it while the API is unreachable.
  document.body.classList.toggle("stale", Boolean(failure));
  page.banner.hidden = !failure;
  if (failure) {
    page.banner.textContent =
      `API unreachable: ${describe(failure.reason)}. Retrying every ${POLL_MS / 1000} seconds.`;
  } else {
    page.updated.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }
}

// Wait for one refresh to finish before planning the next one, so slow
// answers never pile up.
async function poll() {
  await refresh();
  setTimeout(poll, POLL_MS);
}

poll();

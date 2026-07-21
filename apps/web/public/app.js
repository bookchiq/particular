import { createSequencer } from "./sequencer.js";

const form = document.querySelector("#score-form");
const statusLine = document.querySelector("#status");
const results = document.querySelector("#results");
const submitButton = form.querySelector('button[type="submit"]');
const sequencer = createSequencer();
let inFlight = null;
let payload;
let profileOverrides = {};
let lastFile = null;
let lastBasis = null;
// Measures the director locked against transformation, keyed "partId|measure".
const lockedMeasures = new Set();
// Per-part tier choice for the mixed-tier set, keyed by part id (Core default).
let tierAssignments = {};
// Engraving state: the pinned notation library, the OSMD instance bound to the
// preview container, whether the preview is showing, and which tier it shows.
const OSMD_SRC =
  "https://cdn.jsdelivr.net/npm/opensheetmusicdisplay@2.0.0/build/opensheetmusicdisplay.min.js";
let osmdLibraryPromise = null;
let osmd = null;
let notationOpen = false;
let currentTier = "Foundation";

// Resolve the OSMD library, injecting the CDN script once. Tests preload
// window.opensheetmusicdisplay so this resolves without any network use.
function loadOsmdLibrary() {
  if (window.opensheetmusicdisplay)
    return Promise.resolve(window.opensheetmusicdisplay);
  if (osmdLibraryPromise) return osmdLibraryPromise;
  osmdLibraryPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = OSMD_SRC;
    script.crossOrigin = "anonymous";
    script.referrerPolicy = "no-referrer";
    script.onload = () =>
      window.opensheetmusicdisplay
        ? resolve(window.opensheetmusicdisplay)
        : reject(new Error("notation library did not initialize"));
    script.onerror = () => {
      osmdLibraryPromise = null; // allow a later retry
      reject(new Error("notation library failed to load"));
    };
    document.head.append(script);
  });
  return osmdLibraryPromise;
}

// Render the given tier's full-score MusicXML as engraved notation. Engraving
// is online-only (the CDN library) but the score itself never leaves the page.
async function engraveTier(tier) {
  const container = document.querySelector("#notation");
  const status = document.querySelector("#notation-status");
  if (!container) return;
  notationOpen = true;
  status.textContent = "Engraving… loading the notation library.";
  const url = payload.artifacts[tier.toLowerCase()];
  try {
    const library = await loadOsmdLibrary();
    const xml = await (await fetch(url)).text();
    if (!osmd) {
      osmd = new library.OpenSheetMusicDisplay(container, {
        autoResize: true,
        backend: "svg",
        drawTitle: false,
      });
    }
    await osmd.load(xml);
    osmd.render();
    status.textContent = `Showing the ${tier} arrangement.`;
  } catch {
    container.innerHTML = "";
    status.textContent =
      "Couldn’t engrave — this needs an internet connection for the notation library. Try again.";
  }
}

const labels = {
  pitch_range_semitones: "Range · semitones",
  largest_leap_semitones: "Largest leap",
  max_note_density_per_quarter: "Notes / quarter",
  shortest_duration_quarters: "Shortest value",
  accidental_burden: "Accidental burden",
  syncopation: "Syncopation",
  rhythmic_complexity: "Rhythm complexity",
};

async function showLimits() {
  const el = document.querySelector("#upload-limits");
  if (!el) return;
  try {
    const limits = await (await fetch("/api/limits")).json();
    const mb = (bytes) => Math.round(bytes / 1_000_000);
    el.textContent = `.musicxml, .xml, or .mxl · up to ${mb(limits.max_upload_bytes)} MB (expands to ${mb(limits.max_expanded_total_bytes)} MB, ${limits.max_parts} parts)`;
  } catch {
    // Keep the static hint if the limits endpoint is unavailable.
  }
}
showLimits();

async function runGeneration(file, basisValue) {
  // Supersede any in-flight request: take a fresh token and cancel the old fetch.
  const token = sequencer.next();
  if (inFlight) inFlight.abort();
  inFlight = new AbortController();
  submitButton.disabled = true;
  statusLine.textContent = "Listening closely… building coordinated parts.";
  // A new attempt invalidates any previously shown arrangement until it succeeds.
  results.hidden = true;
  let diagnosticRef = "";
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "X-Particular-Filename": file.name,
        "X-Particular-Rights-Basis": basisValue,
        "X-Particular-Instrument-Profiles": JSON.stringify(profileOverrides),
        "X-Particular-Locks": JSON.stringify(
          [...lockedMeasures].map((entry) => entry.split("|")),
        ),
        "X-Particular-Tier-Assignments": JSON.stringify(tierAssignments),
        "Content-Type": "application/octet-stream",
      },
      body: file,
      signal: inFlight.signal,
    });
    const body = await response.json();
    // A newer submission has superseded this one; drop the stale result.
    if (!sequencer.isCurrent(token)) return;
    payload = body;
    if (!response.ok) {
      diagnosticRef = payload.diagnostic_id
        ? ` (ref ${payload.diagnostic_id})`
        : "";
      throw new Error(payload.message || "Your score could not be processed.");
    }
    lastFile = file;
    lastBasis = basisValue;
    render(file.name);
    statusLine.textContent = "Your arrangement family is ready for review.";
    results.hidden = false;
    // Move focus into the results so keyboard and screen-reader users land
    // there; the aria-live status still announces completion.
    const heading = document.querySelector("#results-title");
    if (heading) heading.focus({ preventScroll: true });
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    results.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
      block: "start",
    });
  } catch (error) {
    if (error.name === "AbortError" || !sequencer.isCurrent(token)) return;
    statusLine.textContent = `Could not generate parts: ${error.message}${diagnosticRef}`;
  } finally {
    // Only the latest request restores the control; superseded ones leave it be.
    if (sequencer.isCurrent(token)) submitButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const file = document.querySelector("#score-file").files[0];
  const basis = form.querySelector('input[name="rights-basis"]:checked');
  if (!file || !basis) return;
  lockedMeasures.clear(); // a new upload starts a fresh score
  tierAssignments = {};
  notationOpen = false; // collapse any engraved preview from the previous score
  const notation = document.querySelector("#notation");
  if (notation) notation.innerHTML = "";
  const notationStatus = document.querySelector("#notation-status");
  if (notationStatus) notationStatus.textContent = "";
  runGeneration(file, basis.value);
});

const TIERS = ["Foundation", "Core", "Challenge"];

// Build the tier tablist following the ARIA Tabs pattern: one tab is selected
// with tabindex 0, the rest are -1 (roving tabindex), and each controls the
// shared change-ledger tabpanel.
function renderTabs() {
  const tablist = document.querySelector("#tier-tabs");
  tablist.innerHTML = "";
  TIERS.forEach((tier, index) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.id = `tier-tab-${tier}`;
    tab.role = "tab";
    tab.dataset.tier = tier;
    tab.textContent = tier;
    tab.setAttribute("aria-controls", "changes");
    tab.setAttribute("aria-selected", String(index === 0));
    tab.tabIndex = index === 0 ? 0 : -1;
    tab.addEventListener("click", () => selectTier(tier, { focus: true }));
    tablist.append(tab);
  });
  tablist.onkeydown = onTablistKeydown;
  selectTier(TIERS[0], { focus: false });
}

function selectTier(tier, { focus }) {
  for (const tab of document.querySelectorAll('#tier-tabs [role="tab"]')) {
    const selected = tab.dataset.tier === tier;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  }
  const panel = document.querySelector("#changes");
  if (panel) panel.setAttribute("aria-labelledby", `tier-tab-${tier}`);
  currentTier = tier;
  renderChanges(tier);
  renderScoreMap(tier);
  if (notationOpen) engraveTier(tier);
}

// Index a tier's changes by part and measure so the score map can locate them.
function changesByMeasure(tier) {
  const summary = (payload.manifest.change_summary || {})[tier] || {
    accepted: [],
    rejected: [],
  };
  const located = {};
  const add = (list, kind) =>
    list.forEach((change) => {
      const key = `${change.part_id}|${change.measure}`;
      (located[key] ||= { accepted: [], rejected: [] })[kind].push(change);
    });
  add(summary.accepted, "accepted");
  add(summary.rejected, "rejected");
  return located;
}

function renderScoreMap(tier) {
  const container = document.querySelector("#score-map");
  if (!container) return;
  const located = changesByMeasure(tier);
  const exports = ((payload.part_exports || {})[tier] || []).reduce(
    (map, entry) => {
      map[entry.part_id] = entry.url;
      return map;
    },
    {},
  );
  container.innerHTML = payload.analysis.parts
    .map((part) => {
      const cells = (part.measures || [])
        .map((measure) => {
          const key = `${part.part_id}|${measure}`;
          const at = located[key];
          const locked = lockedMeasures.has(key);
          const state = at?.accepted.length
            ? "changed"
            : at?.rejected.length
              ? "declined"
              : "unchanged";
          const stateLabel =
            state === "changed"
              ? "changed"
              : state === "declined"
                ? "declined candidate"
                : "unchanged";
          const label = `${part.part_name} measure ${measure}: ${locked ? "locked, " : ""}${stateLabel}`;
          return `<button type="button" class="measure ${state}${locked ? " locked" : ""}" data-part="${escapeHtml(part.part_id)}" data-measure="${escapeHtml(measure)}" aria-label="${escapeHtml(label)}">${escapeHtml(measure)}</button>`;
        })
        .join("");
      const url = exports[part.part_id];
      const download = url
        ? `<a class="part-export" href="${url}">${escapeHtml(part.part_name)} part ↓</a>`
        : "";
      return `<div class="score-map-part"><span class="score-map-name">${escapeHtml(part.part_name)}</span><div class="measure-row">${cells}</div>${download}</div>`;
    })
    .join("");
  container.querySelectorAll(".measure").forEach((cell) => {
    cell.addEventListener("click", () =>
      showMeasureDetail(cell.dataset.part, cell.dataset.measure, tier),
    );
  });
  document.querySelector("#score-map-detail").innerHTML = "";
}

function showMeasureDetail(partId, measure, tier) {
  const key = `${partId}|${measure}`;
  const at = changesByMeasure(tier)[key];
  const detail = document.querySelector("#score-map-detail");
  const locked = lockedMeasures.has(key);
  const toggle = `<button type="button" class="lock-toggle" aria-pressed="${locked}">${locked ? "Unlock" : "Lock"} this measure</button>`;
  const body = at
    ? [...at.accepted, ...at.rejected].map(changeArticle).join("")
    : `<p class="ledger-note">Measure ${escapeHtml(measure)}: unchanged in ${escapeHtml(tier)}.</p>`;
  detail.innerHTML = toggle + body;
  detail
    .querySelector(".lock-toggle")
    .addEventListener("click", () => toggleLock(partId, measure, tier));
}

function toggleLock(partId, measure, tier) {
  const key = `${partId}|${measure}`;
  if (lockedMeasures.has(key)) lockedMeasures.delete(key);
  else lockedMeasures.add(key);
  renderScoreMap(tier);
  showMeasureDetail(partId, measure, tier);
  updateRegenerate();
}

function updateRegenerate() {
  const regenerate = document.querySelector("#regenerate");
  if (!regenerate) return;
  const count = lockedMeasures.size;
  regenerate.textContent = count
    ? `Regenerate (${count} locked)`
    : "Regenerate";
}

function onTablistKeydown(event) {
  const tabs = [...document.querySelectorAll('#tier-tabs [role="tab"]')];
  const current = tabs.findIndex(
    (tab) => tab.getAttribute("aria-selected") === "true",
  );
  let next = null;
  if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
  else if (event.key === "ArrowLeft")
    next = (current - 1 + tabs.length) % tabs.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = tabs.length - 1;
  if (next === null) return;
  event.preventDefault();
  selectTier(tabs[next].dataset.tier, { focus: true });
}

function render(sourceName) {
  const source = document.querySelector("#source-name");
  if (source) source.textContent = sourceName ? `Source: ${sourceName}` : "";
  renderTabs();
  document.querySelector("#difficulty").innerHTML = payload.analysis.parts
    .map(
      (part) =>
        `<details class="part" open><summary>${escapeHtml(part.part_name)} · ${escapeHtml(part.profile_id)} (${escapeHtml(part.profile_confidence)})</summary>${part.warning ? `<p>${escapeHtml(part.warning)}</p>` : ""}${part.profile_confidence === "ambiguous" ? `<label class="profile-override">Instrument profile <select data-part-id="${escapeHtml(part.part_id)}">${payload.analysis.available_instrument_profiles.map((profileId) => `<option value="${escapeHtml(profileId)}"${profileOverrides[part.part_id] === profileId ? " selected" : ""}>${escapeHtml(profileId)}</option>`).join("")}</select></label>` : ""}<label class="tier-assign">Mixed-set tier <select class="tier-select" data-tier-part="${escapeHtml(part.part_id)}">${TIERS.map((tier) => `<option value="${tier}"${(tierAssignments[part.part_id] || "Core") === tier ? " selected" : ""}>${tier}</option>`).join("")}</select></label><div class="metrics">${Object.entries(
          labels,
        )
          .map(
            ([key, label]) =>
              `<div class="metric">${label}<strong>${part.vector[key]}</strong></div>`,
          )
          .join("")}</div></details>`,
    )
    .join("");
  document.querySelectorAll("[data-part-id]").forEach((select) => {
    select.addEventListener("change", () => {
      profileOverrides[select.dataset.partId] = select.value;
      statusLine.textContent =
        "Profile selected. Create particular parts again to apply it.";
    });
  });
  document.querySelectorAll("[data-tier-part]").forEach((select) => {
    select.addEventListener("change", () => {
      tierAssignments[select.dataset.tierPart] = select.value;
      updateMixed();
    });
  });
  const names = {
    original: "Normalized original",
    foundation: "Foundation",
    core: "Core",
    challenge: "Challenge",
    manifest: "Change manifest",
    analysis: "Difficulty analysis",
  };
  document.querySelector("#downloads").innerHTML = Object.entries(
    payload.artifacts,
  )
    .map(([key, url]) => `<a href="${url}">${names[key]} ↓</a>`)
    .join("");
  const deleteButton = document.querySelector("#delete-job");
  if (deleteButton) {
    deleteButton.onclick = async () => {
      if (!payload.job_id) return;
      await fetch(`/artifacts/${payload.job_id}`, { method: "DELETE" });
      results.hidden = true;
      statusLine.textContent =
        "Deleted. Your score and generated parts were removed.";
    };
  }
  const regenerate = document.querySelector("#regenerate");
  if (regenerate) {
    regenerate.hidden = false;
    regenerate.onclick = () => {
      if (lastFile) runGeneration(lastFile, lastBasis);
    };
  }
  updateRegenerate();
  renderMixed();
  const engrave = document.querySelector("#engrave");
  if (engrave) engrave.onclick = () => engraveTier(currentTier);
  // A fresh arrangement re-engraves the shown tier so the preview stays current.
  if (notationOpen) engraveTier(currentTier);
}

// The mixed-tier set draws each part from its assigned tier. The build button
// re-runs generation with the current assignments; downloads appear once the
// server has produced the custom set.
function renderMixed() {
  const build = document.querySelector("#build-mixed");
  if (!build) return;
  build.onclick = () => {
    if (lastFile) runGeneration(lastFile, lastBasis);
  };
  const downloads = document.querySelector("#mixed-downloads");
  const custom = payload.custom_set;
  if (custom) {
    downloads.innerHTML =
      `<a href="${custom.url}">Mixed-tier full score ↓</a>` +
      custom.part_exports
        .map(
          (entry) =>
            `<a href="${entry.url}">${escapeHtml(entry.part_name)} · ${escapeHtml(entry.tier)} ↓</a>`,
        )
        .join("");
    downloads.hidden = false;
  } else {
    downloads.innerHTML = "";
    downloads.hidden = true;
  }
  updateMixed();
}

function updateMixed() {
  const build = document.querySelector("#build-mixed");
  if (!build) return;
  const assigned = Object.entries(tierAssignments).filter(
    ([, tier]) => tier && tier !== "Core",
  ).length;
  build.textContent = assigned
    ? `Build mixed-tier set (${assigned} reassigned)`
    : "Build mixed-tier set";
}

const deltaLabels = {
  note_density: "Note density",
  rhythmic_complexity: "Rhythm complexity",
  range: "Range",
};

function formatDelta(value) {
  const rounded = Math.round(value * 100) / 100;
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

function renderDeltas(delta) {
  const entries = Object.entries(delta || {});
  if (!entries.length) return "";
  return `<dl class="deltas" aria-label="Difficulty dimensions changed">${entries
    .map(
      ([key, value]) =>
        `<div><dt>${escapeHtml(deltaLabels[key] || key)}</dt><dd>${escapeHtml(formatDelta(value))}</dd></div>`,
    )
    .join("")}</dl>`;
}

function renderRoleEffects(roleEffects) {
  if (!roleEffects || !roleEffects.length) return "";
  return `<ul class="role-effects" aria-label="Musical roles preserved">${roleEffects
    .map((effect) => `<li>${escapeHtml(effect)}</li>`)
    .join("")}</ul>`;
}

function changeArticle(change) {
  return `<article class="change"><span class="badge ${change.status}">${change.status === "accepted" ? "Accepted change" : "Not applied"}</span><p><strong>${escapeHtml(change.part_id)}, measure ${escapeHtml(change.measure)}</strong> · ${escapeHtml(change.operator)} v${escapeHtml(change.operator_version)}</p><p>${escapeHtml(change.explanation)}</p>${renderDeltas(change.difficulty_delta)}${renderRoleEffects(change.role_effects)}${change.rejection_reason ? `<small>Reason: ${escapeHtml(change.rejection_reason)}</small>` : ""}</article>`;
}

function renderNoops(noops) {
  if (!noops || !noops.count) return "";
  const byOperator = Object.entries(noops.by_operator)
    .map(([operator, count]) => `${escapeHtml(operator)}: ${count}`)
    .join(", ");
  return `<p class="ledger-note">${noops.count} candidate${noops.count === 1 ? "" : "s"} found no applicable change${byOperator ? ` (${byOperator})` : ""}.</p>`;
}

function renderChanges(tier) {
  const summary = (payload.manifest.change_summary || {})[tier] || {
    accepted: [],
    rejected: [],
    rejected_total: 0,
    noops: { count: 0, by_operator: {} },
  };
  const accepted = summary.accepted
    .slice()
    .sort(
      (a, b) =>
        a.part_id.localeCompare(b.part_id) ||
        String(a.measure).localeCompare(String(b.measure)),
    );
  const acceptedHtml =
    accepted.map(changeArticle).join("") ||
    "<p>No changes were applied for this tier.</p>";
  let declinedHtml = "";
  if (summary.rejected_total > 0) {
    const note =
      summary.rejected.length < summary.rejected_total
        ? `<p class="ledger-note">Showing ${summary.rejected.length} of ${summary.rejected_total}. Download the change manifest for the full audit.</p>`
        : "";
    declinedHtml = `<details class="declined"><summary>Show ${summary.rejected_total} declined candidate${summary.rejected_total === 1 ? "" : "s"}</summary>${summary.rejected.map(changeArticle).join("")}${note}</details>`;
  }
  document.querySelector("#changes").innerHTML =
    acceptedHtml + renderNoops(summary.noops) + declinedHtml;
}

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value);
  return span.innerHTML;
}

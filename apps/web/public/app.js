import { createSequencer } from "./sequencer.js";

const form = document.querySelector("#score-form");
const statusLine = document.querySelector("#status");
const results = document.querySelector("#results");
const submitButton = form.querySelector('button[type="submit"]');
const sequencer = createSequencer();
let inFlight = null;
let payload;
let profileOverrides = {};

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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.querySelector("#score-file").files[0];
  const basis = form.querySelector('input[name="rights-basis"]:checked');
  if (!file || !basis) return;
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
        "X-Particular-Rights-Basis": basis.value,
        "X-Particular-Instrument-Profiles": JSON.stringify(profileOverrides),
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
  renderChanges(tier);
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
        `<details class="part" open><summary>${escapeHtml(part.part_name)} · ${escapeHtml(part.profile_id)} (${escapeHtml(part.profile_confidence)})</summary>${part.warning ? `<p>${escapeHtml(part.warning)}</p>` : ""}${part.profile_confidence === "ambiguous" ? `<label class="profile-override">Instrument profile <select data-part-id="${escapeHtml(part.part_id)}">${payload.analysis.available_instrument_profiles.map((profileId) => `<option value="${escapeHtml(profileId)}"${profileOverrides[part.part_id] === profileId ? " selected" : ""}>${escapeHtml(profileId)}</option>`).join("")}</select></label>` : ""}<div class="metrics">${Object.entries(
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

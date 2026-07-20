const form = document.querySelector("#score-form");
const statusLine = document.querySelector("#status");
const results = document.querySelector("#results");
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = document.querySelector("#score-file").files[0];
  const attested = document.querySelector("#rights-attestation").checked;
  if (!file || !attested) return;
  statusLine.textContent = "Listening closely… building coordinated parts.";
  // A new attempt invalidates any previously shown arrangement until it succeeds.
  results.hidden = true;
  let diagnosticRef = "";
  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "X-Particular-Filename": file.name,
        "X-Particular-Rights-Attested": "true",
        "X-Particular-Instrument-Profiles": JSON.stringify(profileOverrides),
        "Content-Type": "application/octet-stream",
      },
      body: file,
    });
    payload = await response.json();
    if (!response.ok) {
      diagnosticRef = payload.diagnostic_id
        ? ` (ref ${payload.diagnostic_id})`
        : "";
      throw new Error(payload.message || "Your score could not be processed.");
    }
    render();
    statusLine.textContent = "Your arrangement family is ready for review.";
    results.hidden = false;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    statusLine.textContent = `Could not generate parts: ${error.message}${diagnosticRef}`;
  }
});

function render() {
  const tabs = document.querySelector("#tier-tabs");
  tabs.innerHTML = "";
  ["Foundation", "Core", "Challenge"].forEach((tier, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.role = "tab";
    button.textContent = tier;
    button.setAttribute("aria-selected", String(index === 0));
    button.onclick = () => {
      tabs
        .querySelectorAll("button")
        .forEach((x) => x.setAttribute("aria-selected", "false"));
      button.setAttribute("aria-selected", "true");
      renderChanges(tier);
    };
    tabs.append(button);
  });
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
  renderChanges("Foundation");
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

function renderChanges(tier) {
  const changes = payload.manifest.changes.filter(
    (change) => change.tier === tier,
  );
  document.querySelector("#changes").innerHTML =
    changes
      .map(
        (change) =>
          `<article class="change"><span class="badge ${change.status}">${change.status === "accepted" ? "Accepted change" : "Not applied"}</span><p><strong>${escapeHtml(change.part_id)}, measure ${escapeHtml(change.measure)}</strong> · ${escapeHtml(change.operator)} v${escapeHtml(change.operator_version)}</p><p>${escapeHtml(change.explanation)}</p>${renderDeltas(change.difficulty_delta)}${renderRoleEffects(change.role_effects)}${change.rejection_reason ? `<small>Reason: ${escapeHtml(change.rejection_reason)}</small>` : ""}</article>`,
      )
      .join("") || "<p>No changes proposed for this tier.</p>";
}

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value);
  return span.innerHTML;
}

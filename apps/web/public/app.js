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
  results.hidden = true;
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
    if (!response.ok) throw new Error(payload.message || payload.error);
    render();
    statusLine.textContent = "Your arrangement family is ready for review.";
    results.hidden = false;
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    statusLine.textContent = `Could not generate parts: ${error.message}`;
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

function renderChanges(tier) {
  const changes = payload.manifest.changes.filter(
    (change) => change.tier === tier,
  );
  document.querySelector("#changes").innerHTML =
    changes
      .map(
        (change) =>
          `<article class="change"><span class="badge ${change.status}">${change.status === "accepted" ? "Accepted change" : "Not applied"}</span><p><strong>${escapeHtml(change.part_id)}, measure ${escapeHtml(change.measure)}</strong></p><p>${escapeHtml(change.explanation)}</p>${change.rejection_reason ? `<small>Reason: ${escapeHtml(change.rejection_reason)}</small>` : ""}</article>`,
      )
      .join("") || "<p>No changes proposed for this tier.</p>";
}

function escapeHtml(value) {
  const span = document.createElement("span");
  span.textContent = String(value);
  return span.innerHTML;
}

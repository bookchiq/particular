// @vitest-environment happy-dom
import { readFileSync } from "node:fs";

import { beforeEach, describe, expect, it, vi } from "vitest";

const html = readFileSync("apps/web/public/index.html", "utf8");
const body = html.slice(html.indexOf("<body>") + 6, html.indexOf("</body>"));

const LIMITS = {
  max_upload_bytes: 16_000_000,
  max_expanded_total_bytes: 80_000_000,
  max_parts: 64,
};

function successPayload(overrides = {}) {
  return {
    review_required: true,
    job_id: "JOB123",
    analysis: {
      available_instrument_profiles: ["viola", "violin"],
      parts: [
        {
          part_id: "P1",
          part_name: overrides.partName ?? "Violin",
          measures: ["1", "2"],
          profile_id: "violin",
          profile_confidence: "declared-instrument",
          warning: null,
          vector: {
            pitch_range_semitones: 7,
            largest_leap_semitones: 5,
            max_note_density_per_quarter: 1,
            shortest_duration_quarters: 1,
            accidental_burden: 0,
            syncopation: 0,
            rhythmic_complexity: 0,
          },
        },
      ],
    },
    manifest: {
      change_summary: {
        Foundation: emptyTier({ count: 2, by_operator: { "octave-range": 2 } }),
        Core: {
          accepted: [
            {
              tier: "Core",
              part_id: "P1",
              measure: "1",
              operator: "rhythm-merge",
              operator_version: 1,
              status: "accepted",
              explanation: "Two adjacent notes merged",
              difficulty_delta: { note_density: -1 },
              role_effects: ["entrance retained"],
              rejection_reason: null,
              locators: [{ part_id: "P1" }],
            },
          ],
          rejected: [],
          rejected_total: 0,
          noops: { count: 0, by_operator: {} },
        },
        Challenge: emptyTier({ count: 0, by_operator: {} }),
      },
    },
    artifacts: {
      original: "/artifacts/JOB123/original",
      foundation: "/artifacts/JOB123/foundation",
      core: "/artifacts/JOB123/core",
      challenge: "/artifacts/JOB123/challenge",
      manifest: "/artifacts/JOB123/manifest",
      analysis: "/artifacts/JOB123/analysis",
    },
    part_exports: {
      Foundation: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/foundation-P1.musicxml",
        },
      ],
      Core: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/core-P1.musicxml",
        },
      ],
      Challenge: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/challenge-P1.musicxml",
        },
      ],
    },
    ...overrides.payload,
  };
}

function emptyTier(noops) {
  return { accepted: [], rejected: [], rejected_total: 0, noops };
}

function jsonResponse(ok, payload) {
  return { ok, json: async () => payload };
}

// Installs a fetch mock. generateResponses is a queue of promises resolved by
// the test so busy-state and out-of-order behavior can be driven precisely.
function installFetch(generateResponses) {
  const deletes = [];
  global.fetch = vi.fn(async (url, options = {}) => {
    if (url === "/api/limits") return jsonResponse(true, LIMITS);
    if (url === "/api/generate") return generateResponses.shift();
    if (options.method === "DELETE") {
      deletes.push(url);
      return jsonResponse(true, { deleted: true });
    }
    throw new Error(`unexpected fetch ${url}`);
  });
  return { deletes };
}

function selectFileAndBasis(name = "demo.musicxml", basis = "public_domain") {
  const fileInput = document.querySelector("#score-file");
  Object.defineProperty(fileInput, "files", {
    configurable: true,
    value: [new File(["<score-partwise/>"], name)],
  });
  document.querySelector(
    `input[name="rights-basis"][value="${basis}"]`,
  ).checked = true;
}

async function loadApp() {
  vi.resetModules();
  await import("../public/app.js");
}

function submit() {
  document
    .querySelector("#score-form")
    .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

beforeEach(() => {
  document.body.innerHTML = body;
  Element.prototype.scrollIntoView = () => {};
});

describe("director review UI", () => {
  it("renders parts, tiers, downloads, and the source filename on success", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();

    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );
    expect(document.querySelector("#status").textContent).toContain(
      "ready for review",
    );
    expect(document.querySelector("#difficulty").textContent).toContain(
      "Violin",
    );
    expect(document.querySelectorAll('#tier-tabs [role="tab"]')).toHaveLength(
      3,
    );
    expect(document.querySelectorAll("#downloads a")).toHaveLength(6);
    expect(document.querySelector("#source-name").textContent).toBe(
      "Source: demo.musicxml",
    );
  });

  it("shows sanitized guidance with a diagnostic ref on a server error", async () => {
    installFetch([
      jsonResponse(false, {
        message: "This score is unsupported.",
        diagnostic_id: "ab12",
      }),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();

    await vi.waitFor(() =>
      expect(document.querySelector("#status").textContent).toContain(
        "This score is unsupported.",
      ),
    );
    expect(document.querySelector("#status").textContent).toContain("ref ab12");
    expect(document.querySelector("#results").hidden).toBe(true);
  });

  it("switches the change ledger between tiers", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Foundation defaults to the no-op summary.
    expect(document.querySelector("#changes").textContent).toContain(
      "found no applicable change",
    );

    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Core");
    coreTab.click();
    expect(document.querySelector("#changes").textContent).toContain(
      "Two adjacent notes merged",
    );
  });

  it("marks the selected tier with aria-selected on keyboard-activatable buttons", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const tabs = [...document.querySelectorAll('#tier-tabs [role="tab"]')];
    expect(tabs.every((tab) => tab.tagName === "BUTTON")).toBe(true);
    tabs[1].click();
    expect(tabs[0].getAttribute("aria-selected")).toBe("false");
    expect(tabs[1].getAttribute("aria-selected")).toBe("true");
  });

  it("uses roving tabindex and links every tab to the ledger tabpanel", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const tabs = [...document.querySelectorAll('#tier-tabs [role="tab"]')];
    expect(tabs.map((tab) => tab.tabIndex)).toEqual([0, -1, -1]);
    expect(
      tabs.every((tab) => tab.getAttribute("aria-controls") === "changes"),
    ).toBe(true);

    const panel = document.querySelector("#changes");
    expect(panel.getAttribute("role")).toBe("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe("tier-tab-Foundation");
  });

  it("navigates tiers with Arrow, Home, and End keys", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const tablist = document.querySelector("#tier-tabs");
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const press = (key) =>
      tablist.dispatchEvent(
        new KeyboardEvent("keydown", { key, bubbles: true }),
      );

    press("ArrowRight");
    expect(tabs[1].getAttribute("aria-selected")).toBe("true");
    expect(tabs[1].tabIndex).toBe(0);
    expect(document.activeElement).toBe(tabs[1]);
    expect(
      document.querySelector("#changes").getAttribute("aria-labelledby"),
    ).toBe("tier-tab-Core");

    press("End");
    expect(tabs[2].getAttribute("aria-selected")).toBe("true");
    press("Home");
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    press("ArrowLeft");
    expect(tabs[2].getAttribute("aria-selected")).toBe("true");
  });

  it("renders a per-part measure map and locates changes by tier", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // One measure cell per measure of each part.
    expect(document.querySelectorAll("#score-map .measure")).toHaveLength(2);
    // Foundation applied nothing, so no measure is highlighted.
    expect(
      document.querySelectorAll("#score-map .measure.changed"),
    ).toHaveLength(0);

    // Core changes P1 measure 1.
    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Core");
    coreTab.click();
    const changed = document.querySelectorAll("#score-map .measure.changed");
    expect(changed).toHaveLength(1);
    expect(changed[0].dataset.measure).toBe("1");

    // Selecting the changed measure explains what happened.
    changed[0].click();
    expect(document.querySelector("#score-map-detail").textContent).toContain(
      "Two adjacent notes merged",
    );
  });

  it("offers a per-part download that follows the selected tier", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    expect(
      document.querySelector("#score-map .part-export").getAttribute("href"),
    ).toBe("/artifacts/JOB123/foundation-P1.musicxml");

    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Core");
    coreTab.click();
    expect(
      document.querySelector("#score-map .part-export").getAttribute("href"),
    ).toBe("/artifacts/JOB123/core-P1.musicxml");
  });

  it("moves focus to the results heading after generation", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    expect(document.activeElement).toBe(
      document.querySelector("#results-title"),
    );
  });

  it("escapes HTML in score-derived text", async () => {
    installFetch([
      jsonResponse(
        true,
        successPayload({ partName: "<img src=x onerror=alert(1)>" }),
      ),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const difficulty = document.querySelector("#difficulty");
    expect(difficulty.querySelector("img")).toBeNull();
    expect(difficulty.innerHTML).toContain("&lt;img");
  });

  it("links every artifact for download", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#downloads a")).toBeTruthy(),
    );

    const hrefs = [...document.querySelectorAll("#downloads a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toContain("/artifacts/JOB123/manifest");
    expect(hrefs).toContain("/artifacts/JOB123/foundation");
  });

  it("disables the submit button while a request is in flight", async () => {
    let resolve;
    const pending = new Promise((r) => {
      resolve = r;
    });
    installFetch([pending]);
    await loadApp();
    selectFileAndBasis();
    const button = document.querySelector('#score-form button[type="submit"]');
    submit();

    await vi.waitFor(() => expect(button.disabled).toBe(true));
    resolve(jsonResponse(true, successPayload()));
    await vi.waitFor(() => expect(button.disabled).toBe(false));
  });

  it("ignores a stale earlier response so only the latest render wins", async () => {
    let resolveFirst;
    const first = new Promise((r) => {
      resolveFirst = r;
    });
    installFetch([
      first,
      jsonResponse(true, successPayload({ payload: { job_id: "SECOND" } })),
    ]);
    await loadApp();

    selectFileAndBasis("first.musicxml");
    submit();
    selectFileAndBasis("second.musicxml");
    submit();

    // The second (fast) response renders first.
    await vi.waitFor(() =>
      expect(document.querySelector("#source-name").textContent).toBe(
        "Source: second.musicxml",
      ),
    );
    // The first (slow) response arrives late and must not overwrite it.
    resolveFirst(
      jsonResponse(true, successPayload({ payload: { job_id: "FIRST" } })),
    );
    await new Promise((r) => setTimeout(r, 10));
    expect(document.querySelector("#source-name").textContent).toBe(
      "Source: second.musicxml",
    );
  });
});

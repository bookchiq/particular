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
        Essential: emptyTier({ count: 2, by_operator: { "octave-range": 2 } }),
        Supported: {
          accepted: [
            {
              tier: "Supported",
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
        Original: emptyTier({ count: 0, by_operator: {} }),
      },
    },
    artifacts: {
      source: "/artifacts/JOB123/source",
      essential: "/artifacts/JOB123/essential",
      supported: "/artifacts/JOB123/supported",
      original: "/artifacts/JOB123/original",
      manifest: "/artifacts/JOB123/manifest",
      analysis: "/artifacts/JOB123/analysis",
    },
    playback: {
      Source: "/artifacts/JOB123/source.playback.json",
      Essential: "/artifacts/JOB123/essential.playback.json",
      Supported: "/artifacts/JOB123/supported.playback.json",
      Original: "/artifacts/JOB123/original.playback.json",
    },
    pdf: {
      available: false,
      note: "PDF export needs MuseScore on the server. Use the MusicXML downloads or the engraved preview instead.",
      exports: {},
    },
    part_exports: {
      Essential: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/essential-P1.musicxml",
        },
      ],
      Supported: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/supported-P1.musicxml",
        },
      ],
      Original: [
        {
          part_id: "P1",
          part_name: "Violin",
          url: "/artifacts/JOB123/original-P1.musicxml",
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

const MUSICXML = "<score-partwise></score-partwise>";

// A two-part timeline (P1: 2 notes, P2: 1 note) so part filtering is observable.
const TIMELINE = {
  tempo_bpm: 90,
  seconds_per_quarter: 0.6667,
  parts: [
    {
      part_id: "P1",
      part_name: "Violin",
      notes: [
        { start: 0, duration: 0.5, midi: 60 },
        { start: 0.5, duration: 0.5, midi: 64 },
      ],
    },
    {
      part_id: "P2",
      part_name: "Viola",
      notes: [{ start: 0, duration: 0.5, midi: 55 }],
    },
  ],
};

// Install a fake Web Audio API so playback scheduling runs without real audio.
// Returns counters the test can assert on.
function installAudio() {
  const calls = { oscillators: 0, started: 0, stopped: 0 };
  class FakeGain {
    constructor() {
      this.gain = { setValueAtTime() {}, linearRampToValueAtTime() {} };
    }
    connect(destination) {
      return destination;
    }
  }
  class FakeOscillator {
    constructor() {
      this.frequency = { value: 0 };
    }
    connect(node) {
      return node;
    }
    start() {
      calls.started += 1;
    }
    stop() {
      calls.stopped += 1;
    }
  }
  class FakeAudioContext {
    constructor() {
      this.currentTime = 0;
      this.destination = {};
    }
    createOscillator() {
      calls.oscillators += 1;
      return new FakeOscillator();
    }
    createGain() {
      return new FakeGain();
    }
    resume() {}
  }
  window.AudioContext = FakeAudioContext;
  return calls;
}

// Install a fake OSMD library so engraving runs without any network or real
// SVG layout. Returns a record of how it was driven.
function installOsmd() {
  const calls = { instances: 0, loads: [], renders: 0 };
  class FakeOSMD {
    constructor(container) {
      this.container = container;
      calls.instances += 1;
    }
    async load(xml) {
      calls.loads.push(xml);
    }
    render() {
      calls.renders += 1;
      this.container.innerHTML = "<svg data-osmd></svg>";
    }
  }
  window.opensheetmusicdisplay = { OpenSheetMusicDisplay: FakeOSMD };
  return calls;
}

// Installs a fetch mock. generateResponses is a queue of promises resolved by
// the test so busy-state and out-of-order behavior can be driven precisely.
function installFetch(generateResponses) {
  const deletes = [];
  global.fetch = vi.fn(async (url, options = {}) => {
    if (url === "/api/limits") return jsonResponse(true, LIMITS);
    if (url === "/api/generate") return generateResponses.shift();
    if (url.startsWith("/artifacts/") && options.method !== "DELETE") {
      if (url.endsWith(".playback.json"))
        return { ok: true, json: async () => TIMELINE };
      return { ok: true, text: async () => MUSICXML };
    }
    if (options.method === "DELETE") {
      deletes.push(url);
      return jsonResponse(true, { deleted: true });
    }
    throw new Error(`unexpected fetch ${url}`);
  });
  return { deletes };
}

// Like installFetch, but records each /api/generate request's options so tests
// can assert on the headers sent (e.g. locked measures).
function installFetchCapturing(generateResponses) {
  const generateBodies = [];
  global.fetch = vi.fn(async (url, options = {}) => {
    if (url === "/api/limits") return jsonResponse(true, LIMITS);
    if (url === "/api/generate") {
      generateBodies.push({ headers: options.headers || {} });
      return generateResponses.shift();
    }
    if (url.startsWith("/artifacts/") && options.method !== "DELETE") {
      if (url.endsWith(".playback.json"))
        return { ok: true, json: async () => TIMELINE };
      return { ok: true, text: async () => MUSICXML };
    }
    if (options.method === "DELETE")
      return jsonResponse(true, { deleted: true });
    throw new Error(`unexpected fetch ${url}`);
  });
  return { generateBodies };
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
  delete window.opensheetmusicdisplay;
  delete window.AudioContext;
  delete window.webkitAudioContext;
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

    // Essential defaults to the no-op summary.
    expect(document.querySelector("#changes").textContent).toContain(
      "Nothing in this tier needed easing",
    );

    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Supported");
    coreTab.click();
    expect(document.querySelector("#changes").textContent).toContain(
      "Two adjacent notes merged",
    );
  });

  it("clears the shown arrangement when a different file is chosen", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Choosing a different file makes the shown result stale — it belongs to
    // the previous score — so the workspace hides it and prompts the next step.
    const fileInput = document.querySelector("#score-file");
    Object.defineProperty(fileInput, "files", {
      configurable: true,
      value: [new File(["<score-partwise/>"], "other.musicxml")],
    });
    fileInput.dispatchEvent(new Event("change", { bubbles: true }));

    expect(document.querySelector("#results").hidden).toBe(true);
    expect(document.querySelector("#status").textContent).toContain("Ready");
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

    // Tabs read Original, Supported, Essential; Essential (last) opens selected.
    const tabs = [...document.querySelectorAll('#tier-tabs [role="tab"]')];
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      "Original",
      "Supported",
      "Essential",
    ]);
    expect(tabs.map((tab) => tab.tabIndex)).toEqual([-1, -1, 0]);
    expect(
      tabs.every((tab) => tab.getAttribute("aria-controls") === "changes"),
    ).toBe(true);

    const panel = document.querySelector("#changes");
    expect(panel.getAttribute("role")).toBe("tabpanel");
    expect(panel.getAttribute("aria-labelledby")).toBe("tier-tab-Essential");
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

    // Focus starts on Essential (the selected tab, last in order); ArrowRight
    // wraps to Original (first).
    press("ArrowRight");
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(tabs[0].tabIndex).toBe(0);
    expect(document.activeElement).toBe(tabs[0]);
    expect(
      document.querySelector("#changes").getAttribute("aria-labelledby"),
    ).toBe("tier-tab-Original");

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
    // Essential applied nothing, so no measure is highlighted.
    expect(
      document.querySelectorAll("#score-map .measure.changed"),
    ).toHaveLength(0);

    // Supported changes P1 measure 1.
    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Supported");
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
    ).toBe("/artifacts/JOB123/essential-P1.musicxml");

    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Supported");
    coreTab.click();
    expect(
      document.querySelector("#score-map .part-export").getAttribute("href"),
    ).toBe("/artifacts/JOB123/supported-P1.musicxml");
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
    expect(hrefs).toContain("/artifacts/JOB123/essential");
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

  it("locks a measure, sends it on regeneration, and preserves it across tiers", async () => {
    const { generateBodies } = installFetchCapturing([
      jsonResponse(true, successPayload()),
      jsonResponse(true, successPayload()),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Regenerate is available and starts with no locks.
    const regenerate = document.querySelector("#regenerate");
    expect(regenerate.hidden).toBe(false);
    expect(regenerate.textContent).toBe("Regenerate");

    // Select a measure, then lock it via the detail toggle.
    const cell = document.querySelector(
      '#score-map .measure[data-measure="1"]',
    );
    cell.click();
    const toggle = document.querySelector("#score-map-detail .lock-toggle");
    expect(toggle.textContent).toContain("Lock");
    toggle.click();

    // The cell reflects the lock and the button now counts it.
    expect(
      document.querySelector('#score-map .measure[data-measure="1"]').classList,
    ).toContain("locked");
    expect(regenerate.textContent).toBe("Regenerate (1 locked)");

    // The lock survives switching tiers.
    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Supported");
    coreTab.click();
    expect(
      document.querySelector('#score-map .measure[data-measure="1"]').classList,
    ).toContain("locked");

    // Regenerating sends the locked measure to the server.
    regenerate.click();
    await vi.waitFor(() => expect(generateBodies).toHaveLength(2));
    const locksHeader = generateBodies[1].headers["X-Particular-Locks"];
    expect(JSON.parse(locksHeader)).toEqual([["P1", "1"]]);
  });

  it("clears locks when a new score is uploaded", async () => {
    const { generateBodies } = installFetchCapturing([
      jsonResponse(true, successPayload()),
      jsonResponse(true, successPayload()),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    document.querySelector('#score-map .measure[data-measure="1"]').click();
    document.querySelector("#score-map-detail .lock-toggle").click();
    expect(document.querySelector("#regenerate").textContent).toBe(
      "Regenerate (1 locked)",
    );

    // A fresh upload resets locks; its request carries an empty lock list.
    selectFileAndBasis("another.musicxml");
    submit();
    await vi.waitFor(() => expect(generateBodies).toHaveLength(2));
    expect(JSON.parse(generateBodies[1].headers["X-Particular-Locks"])).toEqual(
      [],
    );
    await vi.waitFor(() =>
      expect(document.querySelector("#regenerate").textContent).toBe(
        "Regenerate",
      ),
    );
  });

  it("assigns a part to a tier and builds a mixed-tier set with that header", async () => {
    const { generateBodies } = installFetchCapturing([
      jsonResponse(true, successPayload()),
      jsonResponse(
        true,
        successPayload({
          payload: {
            custom_set: {
              url: "/artifacts/JOB123/custom.musicxml",
              part_exports: [
                {
                  part_id: "P1",
                  part_name: "Violin",
                  tier: "Original",
                  url: "/artifacts/JOB123/custom-P1.musicxml",
                },
              ],
            },
          },
        }),
      ),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // No custom set yet, and the build button starts neutral.
    expect(document.querySelector("#mixed-downloads").hidden).toBe(true);
    expect(document.querySelector("#build-mixed").textContent).toBe(
      "Build mixed-tier set",
    );

    // Reassign P1 to Original.
    const select = document.querySelector('[data-tier-part="P1"]');
    select.value = "Original";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    expect(document.querySelector("#build-mixed").textContent).toBe(
      "Build mixed-tier set (1 reassigned)",
    );

    // Building sends the assignment and renders the custom downloads.
    document.querySelector("#build-mixed").click();
    await vi.waitFor(() => expect(generateBodies).toHaveLength(2));
    expect(
      JSON.parse(generateBodies[1].headers["X-Particular-Tier-Assignments"]),
    ).toEqual({ P1: "Original" });

    await vi.waitFor(() =>
      expect(document.querySelector("#mixed-downloads").hidden).toBe(false),
    );
    const links = [...document.querySelectorAll("#mixed-downloads a")];
    expect(links[0].getAttribute("href")).toBe(
      "/artifacts/JOB123/custom.musicxml",
    );
    expect(links[1].getAttribute("href")).toBe(
      "/artifacts/JOB123/custom-P1.musicxml",
    );
    expect(links[1].textContent).toContain("Original");
  });

  it("clears tier assignments on a new upload", async () => {
    const { generateBodies } = installFetchCapturing([
      jsonResponse(true, successPayload()),
      jsonResponse(true, successPayload()),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const select = document.querySelector('[data-tier-part="P1"]');
    select.value = "Essential";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    expect(document.querySelector("#build-mixed").textContent).toContain(
      "1 reassigned",
    );

    // A fresh upload resets assignments; its request carries an empty map.
    selectFileAndBasis("another.musicxml");
    submit();
    await vi.waitFor(() => expect(generateBodies).toHaveLength(2));
    expect(
      JSON.parse(generateBodies[1].headers["X-Particular-Tier-Assignments"]),
    ).toEqual({});
  });

  it("engraves the selected tier and re-engraves when the tier changes", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    const osmd = installOsmd();
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Nothing is engraved until the director asks for it.
    expect(document.querySelector("#notation").innerHTML).toBe("");

    document.querySelector("#engrave").click();
    await vi.waitFor(() => expect(osmd.renders).toBe(1));
    expect(osmd.loads).toEqual([MUSICXML]);
    expect(document.querySelector("#notation svg")).toBeTruthy();
    expect(document.querySelector("#notation-status").textContent).toContain(
      "Showing the Essential arrangement",
    );

    // Switching tiers re-engraves that tier without a second OSMD instance.
    const coreTab = [
      ...document.querySelectorAll('#tier-tabs [role="tab"]'),
    ].find((tab) => tab.textContent === "Supported");
    coreTab.click();
    await vi.waitFor(() => expect(osmd.renders).toBe(2));
    expect(osmd.instances).toBe(1);
    expect(document.querySelector("#notation-status").textContent).toContain(
      "Showing the Supported arrangement",
    );
  });

  it("shows an offline message when engraving fails", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    // A library whose load() rejects stands in for an offline/failed CDN load.
    window.opensheetmusicdisplay = {
      OpenSheetMusicDisplay: class {
        constructor(container) {
          this.container = container;
        }
        async load() {
          throw new Error("unavailable");
        }
        render() {}
      },
    };
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    document.querySelector("#engrave").click();
    await vi.waitFor(() =>
      expect(document.querySelector("#notation-status").textContent).toContain(
        "Couldn’t engrave",
      ),
    );
    expect(document.querySelector("#notation").innerHTML).toBe("");
  });

  it("auditions the selected tier and stops on a second click", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    const audio = installAudio();
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Source options include the normalized source and every tier; default is
    // the reviewed tier (Essential).
    const source = document.querySelector("#audition-source");
    expect([...source.options].map((o) => o.textContent)).toEqual([
      "Source",
      "Essential",
      "Supported",
      "Original",
    ]);
    expect(source.selectedOptions[0].textContent).toBe("Essential");

    // Play schedules every note in the timeline (2 + 1 across two parts).
    document.querySelector("#play").click();
    await vi.waitFor(() => expect(audio.oscillators).toBe(3));
    expect(document.querySelector("#play").textContent).toBe("Stop");
    expect(document.querySelector("#playback-status").textContent).toContain(
      "Playing Essential",
    );

    // A second click stops each of the three active oscillators.
    const stoppedWhilePlaying = audio.stopped;
    document.querySelector("#play").click();
    expect(audio.stopped - stoppedWhilePlaying).toBe(3);
    expect(document.querySelector("#play").textContent).toBe("Play");
    expect(document.querySelector("#playback-status").textContent).toBe(
      "Stopped.",
    );
  });

  it("solos a single part when one is selected", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    const audio = installAudio();
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    // Soloing P1 schedules only P1's two notes, not P2's.
    document.querySelector("#audition-part").value = "P1";
    document.querySelector("#play").click();
    await vi.waitFor(() => expect(audio.oscillators).toBe(2));
    expect(document.querySelector("#playback-status").textContent).toContain(
      "Violin",
    );
  });

  it("reports when Web Audio is unavailable", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    // No installAudio(): window.AudioContext stays undefined.
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    document.querySelector("#play").click();
    await vi.waitFor(() =>
      expect(document.querySelector("#playback-status").textContent).toContain(
        "Web Audio",
      ),
    );
  });

  it("enables a seekable playhead with a time readout during audition", async () => {
    const audio = installAudio();
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    const seek = document.querySelector("#audition-seek");
    const time = document.querySelector("#audition-time");
    expect(seek.disabled).toBe(true); // disabled until playback starts

    document.querySelector("#play").click();
    await vi.waitFor(() => expect(audio.oscillators).toBeGreaterThan(0));
    expect(seek.disabled).toBe(false);
    expect(time.textContent).toContain("/");

    // Dragging the seek bar reschedules playback from the new position.
    const before = audio.oscillators;
    seek.value = "50";
    seek.dispatchEvent(new Event("input", { bubbles: true }));
    expect(audio.oscillators).toBeGreaterThanOrEqual(before);
    expect(time.textContent).toContain("/");
  });

  it("shows the PDF fallback note when MuseScore is unavailable", async () => {
    installFetch([jsonResponse(true, successPayload())]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    expect(document.querySelector("#pdf-note").textContent).toContain(
      "MuseScore",
    );
    expect(document.querySelector("#pdf-downloads").hidden).toBe(true);
  });

  it("lists PDF downloads when the server can render them", async () => {
    installFetch([
      jsonResponse(
        true,
        successPayload({
          payload: {
            pdf: {
              available: true,
              note: "Generated PDFs require director review before rehearsal.",
              exports: {
                Source: "/artifacts/JOB123/source.pdf",
                Essential: "/artifacts/JOB123/essential.pdf",
                Supported: "/artifacts/JOB123/supported.pdf",
                Original: "/artifacts/JOB123/original.pdf",
              },
            },
          },
        }),
      ),
    ]);
    await loadApp();
    selectFileAndBasis();
    submit();
    await vi.waitFor(() =>
      expect(document.querySelector("#results").hidden).toBe(false),
    );

    expect(document.querySelector("#pdf-note").textContent).toContain(
      "director review",
    );
    const pdfDownloads = document.querySelector("#pdf-downloads");
    expect(pdfDownloads.hidden).toBe(false);
    const hrefs = [...pdfDownloads.querySelectorAll("a")].map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs).toContain("/artifacts/JOB123/essential.pdf");
    expect(hrefs).toHaveLength(4);
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

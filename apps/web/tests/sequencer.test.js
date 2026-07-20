import { describe, expect, it } from "vitest";

import { createSequencer } from "../public/sequencer.js";

describe("createSequencer", () => {
  it("supersedes an earlier submission when a second one starts", () => {
    const sequencer = createSequencer();
    const first = sequencer.next();
    const second = sequencer.next();

    expect(sequencer.isCurrent(first)).toBe(false);
    expect(sequencer.isCurrent(second)).toBe(true);
  });

  it("drops an out-of-order response from an earlier request", () => {
    const sequencer = createSequencer();
    const early = sequencer.next();
    const late = sequencer.next();

    // The later request renders...
    expect(sequencer.isCurrent(late)).toBe(true);
    // ...so the slower earlier response is stale and must not render.
    expect(sequencer.isCurrent(early)).toBe(false);
  });

  it("treats a new submission as cancelling the in-flight one", () => {
    const sequencer = createSequencer();
    const inflight = sequencer.next();
    sequencer.next();

    expect(sequencer.isCurrent(inflight)).toBe(false);
  });

  it("issues a fresh, current token when retrying after completion", () => {
    const sequencer = createSequencer();
    const done = sequencer.next();
    expect(sequencer.isCurrent(done)).toBe(true);

    const retry = sequencer.next();
    expect(sequencer.isCurrent(retry)).toBe(true);
    expect(sequencer.isCurrent(done)).toBe(false);
  });
});

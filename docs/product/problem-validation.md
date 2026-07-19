# Problem validation record

## Status

**Provisionally scoped for the hackathon; market validation remains open.** A secondary-research exercise synthesized four director personas from published material. It is useful for pressure-testing product assumptions and choosing a demo scope, but it is not primary research, evidence of demand, or a substitute for design-partner commitments.

For the hackathon only, this synthesis is sufficient to proceed with a prototype. The broader MVP must not treat the director-validation gate as passed until the original interview and design-partner thresholds are met.

## Hypotheses to test

| ID  | Current hypothesis                                                                                                                            | Evidence needed                                                                                                   | Status                                                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| H1  | Mixed-ability ensembles repeatedly require directors to rewrite parts or avoid otherwise desirable repertoire.                                | Recent examples across multiple target directors, including frequency and consequences.                           | Plausible from published accounts; not validated       |
| H2  | Current adaptation imposes meaningful time, monetary, rehearsal, repertoire, or participation costs.                                          | Measured or bounded costs from recent workflows, not general expressions of interest.                             | Time and repertoire costs supported directionally      |
| H3  | Directors can obtain authorized, machine-readable scores often enough for a MusicXML-first product to be useful.                              | Source-format and rights evidence from typical programming decisions.                                             | At risk: print and PDF appear more common              |
| H4  | Three generic coordinated tiers are a useful starting point despite variation among instruments and players.                                  | Directors map recent adaptation decisions to Foundation, Core, and Challenge and identify failures of that model. | Useful demo hypothesis; tier labels remain unvalidated |
| H5  | Directors value ensemble-wide coordination, provenance, explanations, locks, and validation more than independent staff simplification.       | Workflow comparisons and prototype review criteria.                                                               | Strongly supported as a workflow hypothesis            |
| H6  | Directors will review generated parts rather than expecting safe, performance-ready output without expert oversight.                          | Concrete willingness, available review time, and stated acceptance criteria.                                      | Inspectability appears essential; willingness untested |
| H7  | Rights, privacy, and trust constraints can be satisfied by authorization attestation, private processing, deletion, and transparent warnings. | Organizational constraints and unacceptable-use findings.                                                         | Constraints identified; proposed controls unvalidated  |

## Recruitment and sample

The minimum validation sample is five qualifying directors from community, school, or youth ensembles who currently adapt parts or avoid repertoire because of mixed ability. Seek meaningful variation in ensemble context and avoid counting multiple perspectives from one organization as if they demonstrate independent adoption conditions.

Record participant-level recruitment, consent, and notes only in the approved private research system. This repository receives aggregate counts and synthesized themes after review.

| Measure                                                    |                                                                        Gate | Current verified result |
| ---------------------------------------------------------- | --------------------------------------------------------------------------: | ----------------------: |
| Completed qualifying director interviews                   |                                                                  At least 5 |                       0 |
| Independent contexts represented                           |                                                     Report during synthesis |        Not yet measured |
| Design partners with explicit prototype-review commitments |                                                                  At least 3 |                       0 |
| Authorized representative score candidates                 | Report availability and restrictions; no minimum substitutes for validation |        Not yet measured |

### Secondary-research sample

The hackathon synthesis uses four digital-twin personas. These are not participants and do not count toward the interview gate.

| Persona  | Context                                                                  | Grounding strength                                                | Primary pressure on the product                                             |
| -------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Frank    | Experienced high-school orchestra director who adapts his own parts      | Strongest; based on a published step-by-step adaptation account   | Preserve essential musical material while eliminating manual notation entry |
| Maria    | Composite urban high-school string teacher with little arranging support | Limited; mostly inferred from differentiation writing             | Produce useful differentiation quickly without boring advanced players      |
| Victoria | Composite community-orchestra director working with adult volunteers     | Limited; inferred from published interviews and articles          | Preserve dignity, cohesion, and volunteer retention                         |
| Dave     | Composite small-program director with missing instrumentation            | Limited; inferred from differentiation and small-program guidance | Redistribute essential lines to the musicians actually available            |

## Evidence log

Add a row only for an aggregated synthesis batch. Do not include names, organizations, contact information, participant-level notes, private quotations, score titles, or links to restricted material.

| Synthesis date | Interviews included | Context summary                                                                | Evidence artifact or reviewer      | Notes                                                                                        |
| -------------- | ------------------: | ------------------------------------------------------------------------------ | ---------------------------------- | -------------------------------------------------------------------------------------------- |
| 2026-07-19     |                   0 | Four synthetic personas spanning school, community, and small-program contexts | Published-source persona synthesis | Secondary research only; many responses are inferred or invented and cannot establish demand |

## Hackathon synthesis

### Convergent signals

1. **Variants must work simultaneously.** The strongest model is a modified part that can be played alongside original or differently leveled parts, not a collection of unrelated easy editions.
2. **Protect musical invariants and automate mechanical work.** Directors appear to value their judgment about melody, bass, harmony, rhythmic drive, exposed material, and balance. The clearest automation opportunity is transcription, re-entry, and applying reviewable transformations.
3. **Inspection and editing are non-negotiable.** A useful prototype should identify every changed measure, explain the transformation, and export an editable result. It must not present generated output as rehearsal-ready without director review.
4. **Difficulty is instrument-specific.** Range, position, fingering, register, accidentals, leaps, rhythm, endurance, and notation create different burdens on different instruments. A single whole-part difficulty score is inadequate.
5. **Adaptation is partly an ensemble-allocation problem.** Essential material must remain covered somewhere in the ensemble. Simplifying each staff independently could remove melody, bass, harmonic content, rhythmic motion, or cues from the combined result.

### Important divergences and scope risks

- **Difficulty versus missing instrumentation:** Small programs may need redistribution and cross-cueing more urgently than simplification. This is adjacent to the hackathon concept but should not silently expand the first prototype.
- **Pedagogy versus volunteer experience:** School directors may want fingerings and progressive scaffolding; community directors may prioritize confidence, dignity, balance, and avoiding exposed failure.
- **Director time varies sharply:** A workflow that saves an experienced arranger an evening may still be unusable for a teacher who has only one preparation period. The demo should minimize setup and make the result immediately inspectable.
- **MusicXML availability is uncertain:** Published accounts frequently begin with print, manuscript, or PDF. MusicXML remains the right structured input for the prototype, but source acquisition is a major adoption risk rather than a validated assumption.
- **Three tiers may be too generic:** Foundation, Core, and Challenge are reasonable demo vocabulary, but real adaptations may instead use optional notes, divisi, doubling, reassignment, or one-off player-specific changes.

### Demo requirements derived from the synthesis

For the hackathon prototype:

1. accept one authorized MusicXML score;
2. generate coordinated Foundation, Core, and Challenge variants that are intended to be played together;
3. preserve melody, bass, entrances, rhythmic identity, and essential ensemble coverage;
4. apply instrument-aware range and difficulty rules;
5. show changes by part and measure with a short explanation;
6. allow the director to inspect the result and export editable MusicXML;
7. label all output as requiring director review; and
8. keep missing-instrument redistribution out of the first demo unless time remains.

### What this evidence cannot answer

The synthesis cannot establish willingness to use or pay, frequency across the market, actual review time, organizational approval, score availability at scale, or whether the proposed controls satisfy real licensing and privacy requirements. Synthetic expressions of enthusiasm do not count as design-partner commitments.

## Synthesis framework

When at least five qualifying interviews are complete, summarize:

1. recurring workflow stages, tools, handoffs, and failure points;
2. frequency and bounded effort, cost, rehearsal, repertoire, and participation effects;
3. ensemble and instrument contexts in which the problem is strongest or absent;
4. actual source formats and the availability of authorized MusicXML;
5. difficulty dimensions and musical roles directors protect;
6. required review, correction, playback, export, privacy, and deletion controls;
7. differences between expressed enthusiasm and concrete prototype-review commitment;
8. contradictory evidence, outliers, and plausible selection bias;
9. Product Contract assumptions supported, weakened, rejected, or still unknown.

Use counts only where the underlying question and sample make the count meaningful. Do not present five interviews as market-size evidence.

## Decision gate

The full U13 market-validation gate passes only when:

- at least five qualifying interviews show a recurring workflow and measurable pain;
- at least three design partners explicitly agree to review a prototype under the documented criteria;
- the synthesis includes disconfirming evidence and source-format, rights, privacy, and trust findings; and
- the Product Contract is reviewed and revised before engine work if evidence contradicts a core assumption.

Possible outcomes are:

- **Proceed:** evidence supports the problem and the MusicXML-first coordinated-tier workflow.
- **Revise:** the problem is supported, but actors, formats, tiers, controls, or sequencing must change.
- **Pause:** pain is weak, infrequent, already well served, or blocked by score access or rights constraints.
- **Extend research:** the sample is too narrow or evidence conflicts without a clear explanation.

Record a dated decision, the reviewers, and the supporting aggregate synthesis here. Do not change the status based on informal conversations or repository activity alone.

The hackathon has a narrower exception: secondary research may guide a time-boxed, clearly labeled prototype, but it does not change interview counts or validate the business.

## Decision history

| Date       | Decision                                                        | Basis                                                                                                                                      | Product Contract impact                                                                                          |
| ---------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| 2026-07-18 | Research opened; no validation decision                         | Initial project plan only; no interviews completed                                                                                         | None                                                                                                             |
| 2026-07-19 | Proceed with a hackathon prototype; keep market validation open | Four published-source synthetic personas provide enough directional guidance to constrain a demo, but no primary interviews or commitments | Prioritize coordinated, inspectable, instrument-aware MusicXML variants; defer missing-instrument redistribution |

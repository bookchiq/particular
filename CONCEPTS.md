# Canonical concepts

Particular uses these terms consistently in code, APIs, documentation, and the interface.

## Score and structure

- **Score:** A notated musical work containing one or more parts and its global musical structure.
- **Source score:** The immutable MusicXML file supplied by an authorized uploader, identified by checksum.
- **Normalized score:** Particular's canonical, versioned representation of a source score. It preserves source locators and the semantics needed for analysis, transformation, validation, and deterministic export.
- **Passage:** A contiguous musical span used as the unit of analysis or transformation, normally bounded by measures or phrases and identified in musical time.
- **Source locator:** A trace from a normalized or generated event to its source part, measure, voice, and event.

## Difficulty and generation

- **Instrument profile:** Versioned hard constraints and difficulty adjustments for an instrument, including written and sounding ranges, transposition, technique, and endurance considerations.
- **Difficulty vector:** Explainable measurements of a passage's demands, such as range, density, rhythmic subdivision, leaps, endurance, articulations, and polyphony. It is not a universal grade.
- **Tier profile:** Versioned targets and policies for one relative tier: **Foundation**, **Core**, or **Challenge**. The unchanged source remains available as **Original**, which is a comparison state rather than a generated tier.
- **Operator:** A deterministic, versioned transformation that produces one or more alternatives from a passage while retaining provenance.
- **Candidate:** A proposed passage-level result from an operator or constrained AI adapter. A candidate is not accepted output until all applicable validators approve it.
- **Arrangement family:** A mutually compatible set of complete tiered scores generated from one source score, sharing form, landmarks, and musical alignment.
- **Generation:** One immutable, reproducible attempt to produce an arrangement family from a source checksum, configuration, engine build, operator versions, profiles, and random seed.
- **Manifest:** The machine-readable audit record for a generation, including inputs, versions, transformation summaries, warnings, provenance, and timestamps. It separates a **reproducibility** block — every input that determines the output (engine version, normalized-schema version, source checksum and fingerprint, instrument-profile and tier-policy versions, operator versions, profile overrides, and seed), condensed into a `reproducibility_digest` — from **operational** metadata (build identity, generation timestamp, rights attestation) that is recorded but never changes the output.

## Musical safety

- **Protected role:** Essential musical material—such as melody, bass, harmonic support, rhythmic drive, entrances, cues, or exposed material—that a generation must preserve, deliberately reassign, or explicitly fail to transform.
- **Hard constraint:** A rule that generated output may not violate, including duration, alignment, parseability, instrument range, and protected-role coverage.
- **Soft constraint:** A preference used to rank otherwise valid candidates; it can never override a hard constraint.

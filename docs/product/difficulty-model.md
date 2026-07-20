# Difficulty model

Particular describes difficulty as an explainable vector, not a single score or an exam-board grade. The model supports relative transformations within one source score and recognizes that the same passage can demand different skills on different instruments.

## Initial dimensions

- written and sounding range, tessitura, and extremes
- note and onset density
- shortest rhythmic subdivision, syncopation, and tuplet irregularity
- accidentals measured as written relative to the active key signature
- interval size, direction changes, and position or register shifts
- sustained duration, breath demand, repetition, and endurance
- articulation and dynamic complexity
- simultaneous voices, stops, or other polyphony where applicable
- instrument-profile adjustments for transposition and idiomatic technique

Features are computed per measure and then combined into the part-level vector,
so a demanding passage is not hidden by an easy average. Accidental burden counts
notes whose written alteration differs from what the key signature already
implies — a passage in D major is not penalized for its diatonic F♯ — and honors
measure-scoped accidental persistence. Rhythmic complexity is a normalized blend
of subdivision, syncopation (off-beat notes held across a beat), and tuplet
irregularity rather than the shortest value alone.

Every passage retains its vector components and source locators. A tier policy targets reductions across relevant dimensions; it does not require every component to decrease when doing so would damage the music.

## Relative tiers

- **Foundation:** prioritizes rhythmic readability, comfortable range, sustainable execution, clear entrances, and a meaningful ensemble contribution.
- **Core:** reduces the source's main barriers while preserving more rhythmic, melodic, and technical detail.
- **Challenge:** retains most source detail and may regularize only exceptional or non-idiomatic demands.
- **Original:** the unchanged comparison state, not a generated difficulty tier.

The current deterministic policy evaluates each safe transformation against the difficulty
vector for its containing measure. Relevant density and rhythmic features are normalized to a
0–1 pressure and compared with the versioned target for each tier. Foundation therefore accepts
more reductions than Core. Challenge deliberately retains the source's musical detail and only
accepts exceptional range corrections required for instrument safety. If a tier remains unchanged,
its manifest entry says whether no safe candidate exceeded its target or the Challenge fidelity
policy retained the source.

Tier labels never promise equivalence to a school year, examination syllabus, or universal player level. Directors see the changed dimensions and remain responsible for suitability.

## Acceptance boundary

Difficulty reduction is a soft objective. Duration, global alignment, parseability, instrument safety, and protected musical roles are hard constraints. A candidate that is easier but violates a hard constraint is rejected. If no safe candidate exists, Particular retains the passage or reports an explicit unresolved constraint.

Instrument profiles, vector schema, tier policies, and scoring weights are versioned inputs to a generation and recorded in its manifest.

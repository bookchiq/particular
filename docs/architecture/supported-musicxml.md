# Supported MusicXML semantics

Particular currently accepts `score-partwise` MusicXML through a deliberately narrow semantic adapter. “Accepted for analysis” and “safe to export” are separate states: a score may be parsed for a located preflight report while `export_capable` is false. Particular never presents a reconstructed score as canonical when a meaning-bearing construct would be lost.

## Preserved subset

The normalized model and canonical exporter preserve:

- score title, part IDs and part names;
- measure numbers and pickup (`implicit`) state;
- divisions, time signatures, fifths-based key signatures and optional mode;
- chromatic and diatonic part transposition;
- standard clef sign and line;
- textual directions (`words`), placement, and playback tempo from `sound tempo`;
- notes, rests, voices, onsets, durations and chords represented by MusicXML sequencing;
- written pitch spelling (`step`, integer `alter`, and `octave`) as well as sounding pitch;
- note `type`; and
- tie sound (`tie`) and notation (`notations/tied`) state.

Layout-only `print` elements are accepted but regenerated rather than preserved. Source files remain immutable, so omitted layout and non-musical identification metadata remain available in the source artifact.

## Fail-closed subset

The importer records a `CoverageWarning` with part and measure location for meaning-bearing constructs outside the preserved subset. This includes, but is not limited to:

- dynamics, rehearsal marks, metronome directions, wedges and pedal directions;
- articulations, slurs, tuplets, ornaments, technical notation, glissandi and slides;
- lyrics, grace/cue notes, dots, beams, explicit accidentals and staff changes;
- repeats, endings and other barline semantics;
- non-fifths key definitions, clef octave changes and unmodeled attribute state; and
- harmony, figured bass, grouping and other unmodeled measure children.

Any coverage warning makes `Score.export_capable` false. Analysis and preflight may continue, but MusicXML generation and downstream rendering must reject the score until every warning is either supported or explicitly resolved by a future versioned adapter.

The supported subset is a product contract. Adding a construct requires domain representation, import and export behavior, semantic fingerprint coverage, and a round-trip regression test. Removing or narrowing support requires a versioned migration decision.

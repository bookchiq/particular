# Security and authorization

This document records Particular's threat model and the controls that protect it,
for the current **loopback pilot** and as a checklist for a hosted deployment. It
complements [rights and privacy](rights-and-privacy.md) and
[ADR 0003](../architecture/0003-pilot-authorization-model.md).

## Assets

- **Uploaded scores.** A director's source MusicXML may be private,
  pre-publication, or licensed material. This is the most sensitive asset.
- **Generated artifacts.** Tiered scores, per-part exports, playback timelines,
  the analysis report, and the audit manifest derived from an upload.
- **Owner identity.** In the pilot, a per-session principal; in a deployment, an
  authenticated user identity.

## Trust boundaries

- **Pilot:** the only boundary is the local machine. The server binds to
  loopback and refuses non-loopback binds unless explicitly acknowledged (#114).
  Everything runs on, and stays on, the operator's computer.
- **Deployment (future):** the network boundary between a browser and the hosted
  service, and between the service and its artifact storage. This boundary does
  not exist yet and must not be crossed until the gating requirements below are
  met.

## Threats and controls

| Threat                                                  | Control                                                                                                                         |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Accidental public exposure of an unauthenticated server | Loopback-only by default; non-loopback binds refused without explicit acknowledgement (#114).                                   |
| One user reading or deleting another user's job         | Server-side ownership checks on review, download, and delete; a non-owner gets `404`, never a confirmation that the job exists. |
| Guessed or leaked artifact URLs                         | Short-lived signatures over job id, artifact name, owner, and expiry; unsigned, altered, or expired requests are refused.       |
| Indefinite data retention                               | At most eight jobs; each deleted 30 minutes after creation; explicit delete action; everything cleared on shutdown.             |
| Sensitive request metadata in logs                      | The server does not log filenames, paths, or musical request metadata.                                                          |

## Retention, encryption, logging

- **Retention:** ephemeral. Jobs live in a private temporary directory, are
  swept after 30 minutes, and are removed when the server stops. No database, no
  long-term store.
- **Encryption:** transport is plain HTTP on loopback (no network transit).
  Artifacts are **not** encrypted at rest — they are short-lived temp files on
  the operator's own machine. Encryption at rest and TLS in transit are gating
  requirements for a deployment (below), not properties of the pilot.
- **Logging:** deliberately minimal and free of score identifiers.

## Incident boundaries (pilot)

Because the pilot is loopback-only and ephemeral, the blast radius of a fault is
the operator's own machine and the current 30-minute window of jobs. There is no
multi-tenant data to leak and no network attacker in scope. A crash loses
in-flight jobs and nothing else.

## Gating requirements before a hosted deployment

A hosted demo (#69) must not go live until all of these are met (tracked in #24):

- [ ] The principal seam is backed by a **managed authentication provider**.
- [ ] Artifact storage moves off local temp files to storage **encrypted at rest**.
- [ ] **TLS** terminates all transport.
- [ ] **Rate limiting and abuse controls** guard upload and generation.
- [ ] An **authorization matrix** and cross-user access tests cover every
      operation (upload, generation, review, download, delete).
- [ ] Logging, retention, and an incident-response boundary are re-reviewed for
      the multi-tenant, networked threat model.

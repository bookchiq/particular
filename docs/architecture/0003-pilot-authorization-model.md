# ADR 0003: Authorization model for the pilot server

- Status: Accepted
- Date: 2026-07-21

## Context

The demo server has no authentication or per-user authorization. Issue #24
requires server-side ownership checks and short-lived artifact authorization
before Particular is exposed beyond loopback, and a hosted demo (#69) depends on
that work.

ADR 0001 assigns authentication to the TypeScript web application, but that
application is currently a stub (`apps/web/src/index.ts` is empty) — the real
interface is the static demo served by the Python `http.server`. So the pilot
authorization layer lands in the Python demo server, behind a seam that a managed
authentication provider replaces before any real deployment.

The first control already shipped (#114): the server refuses to bind to a
non-loopback interface unless explicitly acknowledged.

## Decision

The pilot authorization model has four parts, each with a clear seam for the
managed, hosted version to replace.

### 1. A principal seam

A single function resolves the **acting owner** for a request — the "principal".
In the pilot it derives a stable per-session identifier from a signed cookie
(sufficient on a single-machine loopback, where different browser sessions stand
in for different users). A managed authentication provider replaces this seam to
return the authenticated user's identity instead. **No code outside the seam
assumes how a principal is established.**

### 2. Job ownership

Every generation job records its owner principal at creation. Reviewing a job's
response, downloading its artifacts, and deleting it all verify that the
request's principal owns the job. A principal that does not own a job receives a
`404` (not a `403`), so the server never confirms that another owner's job
exists.

### 3. Short-lived signed artifact authorization

Artifact URLs carry a signature over the job id, the artifact name, the owner,
and an expiry, using a per-server-instance secret key — replacing permanent
capability URLs. A request with a missing, altered, or expired signature is
refused. Tokens are re-minted on each generation and never outlive the job's
retention window.

### 4. Retention and deletion (unchanged from the loopback model)

At most eight completed jobs are retained, each deleted 30 minutes after
creation (enforced by a background sweep and before every download), with an
explicit "delete these files" action, and everything cleared when the server
stops.

## Gating requirements before any non-loopback deployment

These are hard prerequisites, tracked under #24 / #69, and must not be skipped:

- The **principal seam must be backed by a managed authentication provider** —
  the signed-cookie stand-in is not an authentication system.
- **Artifact storage must move off local temporary files** to storage that is
  encrypted at rest; the pilot's temp directory is not.
- **Transport must be TLS**, terminated by the host or a proxy.
- **Rate limiting and abuse controls** must be added for upload and generation.

## Consequences

- The demo can enforce real per-owner isolation and time-bound artifact access
  today, and those checks are exercised by cross-user tests, so the behaviour is
  proven before a provider is wired in.
- Swapping the pilot cookie principal for a managed provider is a change to one
  seam, not a rewrite of the authorization checks.
- The threat model, retention, logging, and incident boundaries are documented
  in [security and authorization](../product/security-and-authorization.md).

Cross-cutting changes to this model require a superseding ADR.

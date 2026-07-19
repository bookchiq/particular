# Rights and privacy boundary

Particular initially processes only public-domain works, original works, and scores the uploader is authorized to arrange. Before upload processing, a director must attest to one of those bases. Declining the attestation means the file is neither stored nor sent to another service.

This policy is a product safeguard, not legal advice. Generated material is labeled as an arrangement requiring director review; Particular does not grant rights in a source work.

## Data handling principles

- Treat source scores and every derived artifact as private user content.
- Preserve the source unchanged, identify it by checksum, and create immutable derived versions.
- Use opaque object keys and server-side ownership checks for every score and artifact operation.
- Encrypt transport and storage; use short-lived authenticated sessions and expiring downloads.
- Do not put score contents, signed URLs, access tokens, provider credentials, or personal data in logs or job payloads.
- Exclude uploaded and generated material from model training by default.
- Send optional AI providers only the minimum structured feature data required, after a privacy and retention review.
- Keep AI credentials in server-side secret management and out of browsers, manifests, logs, and queued payloads.
- Provide deletion that removes metadata and stored source and derived objects under the documented retention policy.

## Repository boundary

The public repository may contain synthetic scores and public-domain fixtures with recorded provenance. It must not contain private score uploads, contact information, raw interview notes or recordings, credentials, or production artifacts. Corpus intake records authorization and provenance without storing private research data in git.

Retention periods, deletion timing, supported providers, incident response, and production storage controls must be specified and exercised before pilot use.

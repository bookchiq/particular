# Evaluation corpus intake

This directory documents how candidate scores enter Particular's evaluation process. It is not an upload location. Do not commit private scores, interview artifacts, contact details, consent records, credentials, signed permissions, or raw partner feedback here.

## Allowed repository contents

Only commit a score fixture when redistribution is permitted and its provenance and compatible license are documented. Public-domain status must cover both the underlying composition and the particular edition or encoding. A freely downloadable file is not necessarily redistributable.

Private design-partner scores remain in approved access-controlled storage outside git. If code needs to refer to one, use an opaque corpus ID and non-identifying aggregate metadata; never include a title, contributor, organization, storage URL, or reversible identifier.

## Intake workflow

1. **Receive privately.** Use the approved project intake channel, never a GitHub issue, pull request, repository, public chat, or unsolicited attachment.
2. **Confirm authority.** Record whether the work and encoding are original, public domain, openly licensed, or covered by explicit permission to adapt and evaluate. Record permitted uses and jurisdictions where relevant.
3. **Confirm consent and scope.** Document who may access the file, whether derived outputs may be retained or shown, whether external services are allowed, and the withdrawal, retention, and deletion terms.
4. **Minimize metadata.** Inspect for creator/contact fields, comments, revision history, file paths, account identifiers, student information, and unrelated embedded resources. Remove only with the contributor's approval and preserve an untouched source in restricted storage when required.
5. **Quarantine and inspect.** Treat MXL as an untrusted archive and MusicXML as untrusted XML. Before parsing, apply the product's eventual archive-size, entry-count, path, XML entity, resource, and notation-coverage checks. Until those controls exist, do not open private submissions in the application development environment.
6. **Assign an opaque ID.** Keep the mapping between ID, contributor, rights record, and restricted object outside git.
7. **Classify suitability.** Record non-identifying instrumentation, approximate complexity, notation features, expected roles, known hazards, and which evaluation gaps the candidate fills.
8. **Approve or reject.** A designated reviewer confirms rights, privacy, security, and corpus value before the file enters evaluation storage.
9. **Track lifecycle.** Record access, derived artifacts, retention deadline, withdrawal, and confirmed deletion in the private corpus register.

## Minimum private intake record

The access-controlled register should contain:

- opaque corpus ID;
- provenance and rights basis, with supporting permission where applicable;
- contributor consent version and date;
- allowed processing, disclosure, derivative, and retention uses;
- source checksum and storage object reference;
- broad ensemble and notation coverage metadata;
- access group and review decision;
- retention deadline and deletion status;
- restrictions on external rendering, AI services, publication, or model training.

Do not duplicate that register in git.

## Rejection and incident handling

Reject or quarantine material when authority is unclear, consent is incomplete, the file contains personal or student data, the archive or XML appears unsafe, permitted use is incompatible with evaluation, or the score adds no justified corpus coverage. If material arrives through an unapproved channel, restrict access, avoid further copying or processing, notify the project privacy contact through the private process, and delete or return it as required.

## Public fixture promotion

Moving a candidate into the versioned public corpus requires a separate review confirming:

- repository redistribution and creation of derived test artifacts are permitted;
- attribution and license notices are complete;
- the fixture contains no identifying or hidden metadata;
- provenance, checksum, coverage purpose, and expected features are documented; and
- the fixture remains useful without private notes or external restricted context.

Design-partner participation never implies permission to publish a score.

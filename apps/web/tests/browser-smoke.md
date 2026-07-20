# Real-browser smoke flow

DOM-level behavior is covered by `app.test.js` (happy-dom). Because that is not a
real browser, keep this manual smoke as integration confidence — it exercises ES
module loading, `fetch`, file upload, and download/delete against the real demo
server. Run it before release and after any change to `app.js`, `sequencer.js`,
`index.html`, or the demo server.

## Steps

1. Start the demo: `uv run python -m particular.demo --port 8794`.
2. Open `http://127.0.0.1:8794/`.
3. **Module loaded** — the upload hint reads "up to 16 MB (expands to 80 MB, 64
   parts)" (it is populated from `/api/limits`, proving the ES module ran).
4. Select a rights basis, choose
   `evaluation/fixtures/mixed-ensemble-transposition.musicxml`, and submit.
5. **Generation** — results appear with "Source: <filename>", four part-difficulty
   cards, Foundation/Core/Challenge tabs, a bounded change ledger, and six download
   links. Switching tabs re-renders the ledger.
6. **Deletion** — click "Delete these files"; the results hide with a "Deleted."
   message and every download link returns 404.
7. The only expected console error is a `favicon.ico` 404.

This flow is driven with the Playwright MCP tools during development; see the
`particular-browser-testing` note for the exact tool sequence.

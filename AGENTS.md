# Agent instructions

This repository is a reference app for a partner's panel in Dialpad's right
sidebar: a Python server and a Vue panel built on Dialpad's SDK. The
[README](README.md) is the cover, and [`guide/`](guide/) explains everything in
13 chapters and a reference. Read the guide rather than inferring from the code;
it says why, and what the demo fakes.

Start with [1. The big picture](guide/01-the-big-picture.md), then follow the
section for your task.

## Build a partner app from this repository

1. **Ask first.** Before you write code, ask the person for what the repository
   can't tell you:
   - what the panel shows: the open contact's CRM record, or something else,
     such as a call's AI transcript or summary
     ([which chapters you need](guide/01-the-big-picture.md#which-chapters-you-need));
   - the service users connect to, and its OAuth authorize and token URLs and
     scopes;
   - the stack for the server and the panel;
   - their database;
   - where the app runs.
2. **Read [11. Turn the demo into your app](guide/11-from-demo-to-your-app.md).**
   Everything the demo fakes is in `demo/` (on the server and in the panel), and
   the chapter lists the five files where your real code replaces it. The CRM
   record is in `crm/`; an app without one deletes it and the lines tagged
   `crm-record`. Its [tables](guide/11-from-demo-to-your-app.md#every-file) say
   what to do with every file.
3. **Build in chapter order**, 3 to 8: the page, the panel, authentication,
   Connect, the CRM record (CRM apps only), and Dialpad's API. For a panel that
   isn't Vue, use [12. Plain JavaScript](guide/12-plain-javascript.md) or
   [13. React](guide/13-react.md). For a server that isn't Python, follow the
   chapters and [`contract/openapi.json`](contract/openapi.json).
4. **Don't ship the demo's shortcuts:** anything in `demo/` (the storage cookie,
   the in-memory OAuth results, the fake authorize page), or local mode in
   production.
5. **Deploy** as [`deployment/README.md`](deployment/README.md) describes: the
   container image, the environment variables and secrets it needs, and Cloud
   Run. Any container host works the same way.

You're done when every row of [9. Security checklist](guide/09-security-checklist.md)
holds for the app, and its tests pass ([chapter 10](guide/10-test-your-app.md)).

## Contribute to this repository

- **The layout** is in the README's [repository table](README.md#the-repository),
  and each module's docstring or header comment says what it does.
- **Run the checks** in [10. Test your app](guide/10-test-your-app.md#run-the-checks)
  before you commit. CI runs the same ones.
- **Keep the guide true.** A change to what the code does updates the chapter
  that describes it in the same pull request, including the
  [tables in chapter 11](guide/11-from-demo-to-your-app.md#every-file)
  when you add, rename, or delete a file.
- **Make the guide's code work as shown.** Partners copy its snippets: declare
  every variable a snippet reads, or say where it comes from, and type-check a
  TypeScript snippet against the vendored SDK.
- **Check what the guide says about the SDK against the SDK's code**, in
  `client/node_modules/@dialpad/dialapp-external-sdk`, not against an earlier
  version.
- **Keep the server's security checks true.** A change to the idtoken, the
  storage cookie, the Content-Security-Policy, or framing keeps every row of
  [9. Security checklist](guide/09-security-checklist.md) true.
- **Write docs in the Dialpad writing style guide.** The most common misses are
  time-relative words (now, new, older, used to), passive voice, ambiguous
  pronouns, and "screenshot" for "image". `pnpm format:ci` in `client/` checks
  the Markdown formatting, and `pnpm links:ci` its links.
- **Regenerate the guide's images** after a change to the panel's look
  ([`guide/images/`](guide/images/README.md)). Images show fake data only.
- **Vendor a new SDK build** with `pnpm run vendor <dir>` in `client/`. Each
  tarball carries a new version number
  ([chapter 2](guide/02-run-the-demo.md#upgrade-the-sdk)). Copy
  `contract/openapi.json` from the same SDK commit: its `info.version` names the
  tarball's version, and the SDK's CI requires the two to be identical.
- **Use public packages only.** The repository installs nothing from Dialpad's
  private registry.
- **Never commit secrets.** Client secrets, idtokens, and API keys stay out of
  files, including tests and docs.
- **Commit messages** start with the Jira ticket, or `NO-JIRA:`.

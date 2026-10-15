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
   - their CRM, and its OAuth authorize and token URLs and scopes;
   - the stack for the server and the panel;
   - their database;
   - where the app runs.
2. **Read [11. Turn the demo into your app](guide/11-from-demo-to-your-app.md).**
   Its [tables](guide/11-from-demo-to-your-app.md#what-to-keep-change-and-delete)
   say which files to keep, change, and delete. Everything the demo fakes is in
   them.
3. **Build in chapter order**, 3 to 8: the page, the panel, authentication,
   Connect, the CRM record, and Dialpad's API. For a panel that isn't Vue, use
   [12. Plain JavaScript](guide/12-plain-javascript.md) or
   [13. React](guide/13-react.md). For a server that isn't Python, follow the
   chapters and [`contract/openapi.json`](contract/openapi.json).
4. **Don't ship the demo's shortcuts:** the session cookie, the in-memory OAuth
   results, the fake authorize page, or local mode in production.

You're done when every row of [9. Security checklist](guide/09-security-checklist.md)
holds for the app, and its tests pass ([chapter 10](guide/10-test-your-app.md)).

## Contribute to this repository

- **The layout** is in the README's [repository table](README.md#the-repository),
  and each module's docstring or header comment says what it does.
- **Run the checks** in [10. Test your app](guide/10-test-your-app.md#run-the-checks)
  before you commit. CI runs the same ones.
- **Keep the guide true.** A change to what the code does updates the chapter
  that describes it in the same pull request, including the
  [tables in chapter 11](guide/11-from-demo-to-your-app.md#what-to-keep-change-and-delete)
  when you add, rename, or delete a file.
- **Write docs in the Dialpad writing style guide.** `pnpm format:ci` in
  `client/` checks the Markdown formatting.
- **Regenerate the guide's images** after a change to the panel's look
  ([`guide/images/`](guide/images/README.md)). Images show fake data only.
- **Vendor a new SDK build** with `pnpm run vendor <dir>` in `client/`. Each
  tarball carries a new version number
  ([chapter 2](guide/02-run-the-demo.md#upgrade-the-sdk)).
- **Use public packages only.** The repository installs nothing from Dialpad's
  private registry.
- **Never commit secrets.** Client secrets, idtokens, and API keys stay out of
  files, including tests and docs.
- **Commit messages** start with the Jira ticket, or `NO-JIRA:`.

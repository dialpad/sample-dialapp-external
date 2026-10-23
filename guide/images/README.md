# Images

The guide uses images only where they show something the text can't, mostly
Dialpad's own UI.

| Image                 | Shown in                                                         | How it's made                                                                 |
| --------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `dialpad-sidebar.png` | [Chapter 1](../01-the-big-picture.md)                            | Captured by hand in dialpadbeta, with the real contact replaced by a fake one |
| `dev-host.png`        | [Chapter 2](../02-run-the-demo.md#run-it-locally)                | `pnpm run guide:images` in `client/`                                          |
| `panel-318.png`       | [Chapter 4](../04-build-the-panel.md#design-for-the-panels-size) | `pnpm run guide:images` in `client/`                                          |
| `panel-250.png`       | [Chapter 4](../04-build-the-panel.md#design-for-the-panels-size) | `pnpm run guide:images` in `client/`                                          |

To add:

- **The panel header's View Contact link and button, and the panel menu**, for
  [chapter 7](../07-show-the-crm-record.md#link-the-record-in-dialpad). Captured
  by hand in dialpadbeta, once Dialpad's `set/menu` is live there.

## Conventions

- **Regenerate** the dev host images after a change to the panel's look. Start
  the server in local mode and Vite first ([chapter 2](../02-run-the-demo.md#run-it-locally)).
- **PNG at twice the CSS size**, cropped to what matters. Set the `width` in the
  `<img>` tag to the CSS size.
- **Fake data only.** Use the dev host's contacts, or test contacts in
  dialpadbeta, never real names, numbers, or emails.
- **Alt text** describes what the image shows.
- **In the text, say "image"**, not "screenshot".

// Checks every relative link in the repository's Markdown: the file it points to exists, and so
// does the heading its #anchor names.
//
// This repository's own tooling, for the people who maintain this guide. A partner's app doesn't
// need it.
//
//   pnpm links:ci
//
// It reads the same Markdown that `pnpm format:ci` checks, finds Markdown links and images, and
// the `src` and `href` of HTML tags, then prints each broken one as `file:line` and exits with
// status 1. Links to other sites (`https:`, `mailto:`) aren't checked. Anchors are checked only
// in Markdown files, using GitHub's rules for heading IDs. It needs no packages of its own.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** The repository root (this file lives in `client/scripts/`). */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
/** The Markdown to check, relative to the root: files, or folders searched for `.md` files. */
const SOURCES = [
  'README.md',
  'AGENTS.md',
  'guide',
  'contract/README.md',
  'deployment/README.md',
  'client/e2e',
];
/** A Markdown link or image, `[text](target)`, or an HTML `src` or `href`. Group 1 or 2 is the target. */
const LINK = /\]\(([^)\s]+)(?:\s+"[^"]*")?\)|\b(?:src|href)="([^"]+)"/g;

/** Every `.md` file under `path`, or `path` itself when it's a file. */
function markdownFiles(path) {
  if (!statSync(path).isDirectory()) {
    return [path];
  }
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) => {
    const child = join(path, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(child);
    }
    return extname(entry.name) === '.md' ? [child] : [];
  });
}

/**
 * `text` with its fenced code blocks and inline code blanked out, so links inside code are
 * skipped. Each character is replaced with a space and newlines are kept, so line numbers match.
 */
function withoutCode(text) {
  const blank = (code) => code.replace(/[^\n]/g, ' ');
  return text
    .replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, blank)
    .replace(/`[^`\n]*`/g, blank);
}

/** The ID GitHub gives a heading: lowercase, punctuation removed, spaces turned into hyphens. */
function headingId(heading) {
  const text = heading
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // a link: keep its text
    .replace(/[`*]/g, '')
    .replace(/<[^>]+>/g, '');
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s_-]/gu, '')
    .replace(/\s/g, '-');
}

/** The anchors a Markdown file has. GitHub adds `-1`, `-2` and so on to repeated headings. */
const anchorsByFile = new Map();
function anchors(file) {
  let found = anchorsByFile.get(file);
  if (!found) {
    found = new Set();
    const counts = new Map();
    for (const match of withoutCode(readFileSync(file, 'utf8')).matchAll(
      /^#{1,6}\s+(.+)$/gm,
    )) {
      const id = headingId(match[1]);
      const count = counts.get(id) ?? 0;
      counts.set(id, count + 1);
      found.add(count === 0 ? id : `${id}-${count}`);
    }
    anchorsByFile.set(file, found);
  }
  return found;
}

/** The problem with `target`, a link in `file`, or `null` when it resolves. */
function problem(file, target) {
  if (/^[a-z][a-z+.-]*:/i.test(target)) {
    return null; // another site, or mailto:
  }
  const hash = target.indexOf('#');
  const path = hash === -1 ? target : target.slice(0, hash);
  const anchor = hash === -1 ? '' : decodeURIComponent(target.slice(hash + 1));
  const linked = path ? resolve(dirname(file), decodeURIComponent(path)) : file;
  if (!existsSync(linked)) {
    return `no file at ${relative(root, linked)}`;
  }
  if (anchor && extname(linked) === '.md' && !anchors(linked).has(anchor)) {
    return `no heading for #${anchor} in ${relative(root, linked)}`;
  }
  return null;
}

const broken = [];
for (const file of SOURCES.flatMap((source) =>
  markdownFiles(join(root, source)),
)) {
  const text = withoutCode(readFileSync(file, 'utf8'));
  for (const match of text.matchAll(LINK)) {
    const target = match[1] ?? match[2];
    const reason = problem(file, target);
    if (reason) {
      const line = text.slice(0, match.index).split('\n').length;
      broken.push(`${relative(root, file)}:${line}: ${target} (${reason})`);
    }
  }
}

if (broken.length > 0) {
  console.error(`links: ${broken.length} broken:\n${broken.join('\n')}`);
  process.exit(1);
}
console.log('links: every relative link resolves');

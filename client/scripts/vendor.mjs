// Pulls a new copy of Dialpad's SDK into vendor/ and installs it.
//
//   pnpm run vendor <dir>
//
// <dir> holds exactly one dialpad-dialapp-external-sdk-<version>.tgz; any other file in it is
// ignored. The script replaces everything in vendor/ with that tarball, points package.json at it,
// then installs the packages into node_modules. Run it from client/ (`pnpm run vendor <dir>`). Running it twice with the same file gives the same result. It
// needs no packages of its own. The server has no copy of the library: it installs only public
// Python packages.
import { spawnSync } from 'node:child_process';
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** The client/ folder (this file lives in `scripts/`). */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
/** The file name the SDK's packaging produces; the capture group is the version. */
const SDK = /^dialpad-dialapp-external-sdk-(.+)\.tgz$/;

/** Print a `vendor:` error and exit with status 1. Nothing after it runs. */
function fail(message) {
  console.error(`vendor: ${message}`);
  process.exit(1);
}

/** Return the one file name in `files` that matches `pattern`, or fail if there are none or many. */
function findOne(files, pattern, description, dir) {
  const matches = files.filter((file) => pattern.test(file));
  if (matches.length === 0) {
    fail(`no ${description} found in ${dir}`);
  }
  if (matches.length > 1) {
    fail(
      `expected one ${description} in ${dir}, found ${matches.length}: ${matches.join(', ')}`,
    );
  }
  return matches[0];
}

/** Replace the first match of `pattern` in the file at `path`, failing if there is no match. */
function replaceOnce(path, pattern, replacement, description) {
  const text = readFileSync(path, 'utf8');
  if (!pattern.test(text)) {
    fail(`${description} not found in ${path}`);
  }
  writeFileSync(path, text.replace(pattern, replacement));
}

/** Run a command in the repository root with its output shown, failing if it does not exit 0. */
function run(command, args) {
  console.log(`vendor: $ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit' });
  if (result.status !== 0) {
    fail(`\`${command} ${args.join(' ')}\` failed`);
  }
}

const argument = process.argv[2];
if (!argument || process.argv.length > 3) {
  fail('usage: pnpm run vendor <dir containing the SDK .tgz>');
}
const source = resolve(argument);
if (!existsSync(source)) {
  fail(`${source} does not exist`);
}

const files = readdirSync(source);
const sdk = findOne(
  files,
  SDK,
  'SDK tarball (dialpad-dialapp-external-sdk-<version>.tgz)',
  source,
);

// Replace vendor/ with the tarball.
const vendor = join(root, 'vendor');
rmSync(vendor, { recursive: true, force: true });
mkdirSync(vendor);
copyFileSync(join(source, sdk), join(vendor, sdk));

// Point package.json at it.
replaceOnce(
  join(root, 'package.json'),
  /("@dialpad\/dialapp-external-sdk":\s*")file:vendor\/[^"]+(")/,
  `$1file:vendor/${sdk}$2`,
  'the @dialpad/dialapp-external-sdk dependency',
);

// Install. The lockfile's checksum for the tarball changes with every build, even at the same
// version, so the install is not frozen.
run('pnpm', ['install', '--no-frozen-lockfile']);

console.log(`vendor: done. SDK ${sdk}`);

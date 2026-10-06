// Pulls new copies of Dialpad's two libraries into vendor/ and installs them.
//
//   pnpm run vendor <dir>
//
// <dir> holds exactly one dialpad-dialapp-external-sdk-<version>.tgz and one
// dialpad_dialapp_toolkit-<version>-py3-none-any.whl (the libraries' `artifacts/` folder).
// The script replaces everything in vendor/ with those two files, points package.json and
// requirements.txt at them, then installs them into node_modules and .venv. Running it twice with
// the same files gives the same result. It needs no packages of its own.
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

/** The repository root (this file lives in `scripts/`). */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
/** The file names the libraries' packaging produces; the capture group is the version. */
const SDK = /^dialpad-dialapp-external-sdk-(.+)\.tgz$/;
const TOOLKIT = /^dialpad_dialapp_toolkit-(.+)-py3-none-any\.whl$/;

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
  fail('usage: pnpm run vendor <dir containing the .tgz and the .whl>');
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
const toolkit = findOne(
  files,
  TOOLKIT,
  'toolkit wheel (dialpad_dialapp_toolkit-<version>-py3-none-any.whl)',
  source,
);

const python = join(root, '.venv', 'bin', 'python');
if (!existsSync(python)) {
  fail(
    '.venv/bin/python not found; create it first (python3.14 -m venv .venv)',
  );
}

// Replace vendor/ with the two files.
const vendor = join(root, 'vendor');
rmSync(vendor, { recursive: true, force: true });
mkdirSync(vendor);
copyFileSync(join(source, sdk), join(vendor, sdk));
copyFileSync(join(source, toolkit), join(vendor, toolkit));

// Point the two references at them.
replaceOnce(
  join(root, 'package.json'),
  /("@dialpad\/dialapp-external-sdk":\s*")file:vendor\/[^"]+(")/,
  `$1file:vendor/${sdk}$2`,
  'the @dialpad/dialapp-external-sdk dependency',
);
replaceOnce(
  join(root, 'requirements.txt'),
  /^\.\/vendor\/.*\.whl$/m,
  `./vendor/${toolkit}`,
  'the ./vendor/...whl line',
);

// Install them. The lockfile's checksum for the tarball changes with every build, even at the same
// version, so the install is not frozen. The wheel is force-reinstalled for the same reason: pip
// would otherwise keep an already-installed copy of the same version.
run('pnpm', ['install', '--no-frozen-lockfile']);
run(python, [
  '-m',
  'pip',
  'install',
  '--force-reinstall',
  '--no-deps',
  `./vendor/${toolkit}`,
]);
run(python, ['-m', 'pip', 'install', '-r', 'requirements-dev.txt']);

console.log(`vendor: done. SDK ${sdk}, toolkit ${toolkit}`);

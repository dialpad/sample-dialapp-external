// Keeps contract/openapi.json identical to the contract the installed SDK ships.
//
// This repository's own tooling. A partner's app doesn't need it.
//
//   pnpm sync:contract   copies the SDK's openapi.json over contract/openapi.json
//   pnpm contract:ci     fails when the two differ, and says to run `pnpm sync:contract`
//
// The SDK package carries the contract as `@dialpad/dialapp-external-sdk/openapi.json`, so an SDK
// upgrade changes the contract with it. Run `pnpm sync:contract` in the same commit as the upgrade.
// It needs no packages of its own.
import { copyFileSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/** The repository root (this file lives in `client/scripts/`). */
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const ours = resolve(root, 'contract', 'openapi.json');
const sdkName = '@dialpad/dialapp-external-sdk/openapi.json';
const sdk = createRequire(import.meta.url).resolve(sdkName);

if (process.argv.includes('--check')) {
  if (!readFileSync(ours).equals(readFileSync(sdk))) {
    console.error(
      `contract: contract/openapi.json differs from the installed ${sdkName}. ` +
        'Run `pnpm sync:contract` in client/ and commit the result.',
    );
    process.exit(1);
  }
  console.log('contract: contract/openapi.json matches the installed SDK');
} else {
  copyFileSync(sdk, ours);
  console.log(
    `contract: copied the installed ${sdkName} to contract/openapi.json`,
  );
}

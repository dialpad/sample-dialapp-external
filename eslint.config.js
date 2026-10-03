// A short public ESLint setup. The house rules at the end come from Dialpad's internal
// @dialpad/eslint-config, copied here so this repository installs from public packages only.
import js from '@eslint/js';
import vitest from '@vitest/eslint-plugin';
import prettier from 'eslint-config-prettier';
import { defineConfig } from 'eslint/config';
import pluginVue from 'eslint-plugin-vue';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default defineConfig(
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      '.venv/**',
      'vendor/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...pluginVue.configs['flat/recommended'],
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: {
        projectService: true,
        extraFileExtensions: ['.vue'],
      },
    },
  },
  {
    // .vue files need the TypeScript parser inside eslint-plugin-vue's parser.
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    files: ['**/*.test.ts'],
    ...vitest.configs.recommended,
  },
  {
    files: ['*.config.{js,ts}', 'e2e/**/*.ts'],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    files: ['**/*.js'],
    ...tseslint.configs.disableTypeChecked,
  },
  prettier,
  {
    rules: {
      eqeqeq: ['error', 'smart'],
      // The contract's JSON is snake_case, so object properties are exempt.
      camelcase: ['error', { properties: 'never' }],
      complexity: ['error', 9],
      'default-param-last': 'error',
      'array-callback-return': 'error',
      'prefer-const': 'error',
      'no-var': 'error',
      curly: 'error',
    },
  },
);

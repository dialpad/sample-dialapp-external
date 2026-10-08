// The same options as @dialpad/prettier-config (an internal package), so this repository formats
// exactly like Dialpad's libraries without depending on Dialpad's private registry.

/**
 * @type {import("prettier").Config}
 */
export default {
  singleQuote: true,
  trailingComma: 'all',
  proseWrap: 'always',
  // HTML whitespace is significant, so prettier leaves at least one whitespace character between
  // elements separated by any amount of whitespace.
  htmlWhitespaceSensitivity: 'ignore',
  embeddedLanguageFormatting: 'off',

  // Needed for <script> and <style> in .vue files, and for code fences in .md files.
  overrides: [
    {
      files: ['*.vue', '*.md', '*.mdx'],
      options: {
        embeddedLanguageFormatting: 'auto',
      },
    },
  ],
};

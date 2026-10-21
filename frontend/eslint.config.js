// ESLint 9 flat configuration for the Holly dashboard: the recommended JavaScript and
// TypeScript rules, the React hooks rules, the fast-refresh export check, and the SonarQube
// rules the App Store's Code Quality stage has failed an upload on.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      // The two classic hooks rules, as the dashboard has always been linted; the plugin's
      // newer compiler-based rules are not enabled.
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // SonarQube rules the App Store gate counts, checked here so they never reach it:
      // S2004, no function nested more than 4 deep; S4138, for-of over an index loop;
      // S6557, startsWith and endsWith over an anchored regular expression; S7723, a built-in
      // constructor called with new.
      "no-restricted-syntax": [
        "error",
        {
          selector: ":function :function :function :function :function",
          message: "Do not nest functions more than 4 levels deep (SonarQube S2004).",
        },
        {
          selector:
            "CallExpression[callee.type='Identifier'][callee.name=/^(Array|ArrayBuffer|DataView|Date|Error|EvalError|RangeError|ReferenceError|SyntaxError|TypeError|URIError|AggregateError|Function|Map|WeakMap|Set|WeakSet|Promise|RegExp|Proxy|WeakRef|FinalizationRegistry|SharedArrayBuffer|(Ui|I)nt(8|16|32)Array|Uint8ClampedArray|Float(32|64)Array|Big(Ui|I)nt64Array)$/]",
          message: "Call a built-in constructor with new (SonarQube S7723).",
        },
      ],
      "@typescript-eslint/prefer-for-of": "error",
    },
  },
  {
    // S6557 needs type information, so it reads the TypeScript project, which covers src.
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: { "@typescript-eslint/prefer-string-starts-ends-with": "error" },
  },
  {
    // Tests and their support files are never hot-reloaded, so the fast-refresh check is off.
    files: ["src/test/**", "src/**/*.test.{ts,tsx}"],
    rules: { "react-refresh/only-export-components": "off" },
  },
);

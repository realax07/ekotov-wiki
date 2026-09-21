// ESLint config for ekotov-wiki frontend (ES2022 modules, browser)
// H4: линтер в воротах. Библиотеки не используются — только нативный JS.
module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
  },
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
  },
  extends: ["eslint:recommended"],
  rules: {
    // XSS-дисциплина проекта: только createElement + textContent
    "no-unsanitized/no-unsanitized": "off", // плагин не подключен; правило дублируется ревью
    "no-eval": "error",
    "no-implied-eval": "error",
  },
  ignorePatterns: ["**/artifacts/", "**/__pycache__/"],
};

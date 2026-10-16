/* rich/highlight.js — подсветка синтаксиса кода (tasks.md 2.3б; design §2;
 * FR-122, ОГР-8).
 *
 * СОБСТВЕННЫЙ токенайзер (vanilla, БЕЗ внешних CDN/библиотек — NFR-33):
 * базовые классы токенов — ключевые слова / строки / комментарии / числа.
 * Результат — DOM-узлы через createElement/textContent (XSS: содержимое
 * код-блока всегда текст, NFR-35); переносы/пробелы — буквально.
 */

"use strict";

/* Семейства языков: ключевые слова и стиль комментариев. */
var LANGS = {
  python: {
    keywords: "and as assert async await break class continue def del elif else except False finally for from global if import in is lambda None nonlocal not or pass raise return True try while with yield".split(" "),
    hashComment: true,
  },
  javascript: {
    keywords: "async await break case catch class const continue debugger default delete do else export extends false finally for function if import in instanceof let new null of return static super switch this throw true try typeof var void while with yield".split(" "),
    slashComment: true,
  },
  css: {
    keywords: "color background border margin padding display flex grid width height font".split(" "),
    slashComment: false,
    blockComment: true,
  },
  json: {
    keywords: "true false null".split(" "),
  },
  html: {
    keywords: [],
  },
};

var TOKEN_CLASSES = {
  kw: "rich-tok-kw",
  str: "rich-tok-str",
  com: "rich-tok-com",
  num: "rich-tok-num",
};

/* Токенайзер: последовательность [класс, текст]; неизвестный класс —
 * обычный текст. Порядок правил: комментарий → строка → число/слово. */
export function tokenize(code, lang) {
  var rules = LANGS[lang] || null;
  var tokens = [];
  var i = 0;
  var n = code.length;

  function push(cls, text) {
    if (!text) return;
    var last = tokens[tokens.length - 1];
    if (last && last[0] === cls) last[1] += text;
    else tokens.push([cls, text]);
  }

  while (i < n) {
    var rest = code.slice(i);
    var match;

    if (rules && rules.hashComment && rest.charAt(0) === "#") {
      var nl = rest.indexOf("\n");
      var end = nl === -1 ? rest.length : nl;
      push("com", rest.slice(0, end));
      i += end;
      continue;
    }
    if (rules && rules.slashComment && rest.slice(0, 2) === "//") {
      var nl2 = rest.indexOf("\n");
      var end2 = nl2 === -1 ? rest.length : nl2;
      push("com", rest.slice(0, end2));
      i += end2;
      continue;
    }
    if (rules && rules.blockComment && rest.slice(0, 2) === "/*") {
      var close = rest.indexOf("*/", 2);
      var end3 = close === -1 ? rest.length : close + 2;
      push("com", rest.slice(0, end3));
      i += end3;
      continue;
    }
    if ((match = /^(?:"(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?|`(?:[^`\\]|\\.)*`?)/.exec(rest)) !== null) {
      push("str", match[0]);
      i += match[0].length;
      continue;
    }
    if ((match = /^0[xX][0-9a-fA-F]+|^\d+(?:\.\d+)?/.exec(rest)) !== null) {
      push("num", match[0]);
      i += match[0].length;
      continue;
    }
    if (rules && (match = /^[A-Za-z_$][A-Za-z0-9_$]*/.exec(rest)) !== null) {
      push(rules.keywords.indexOf(match[0]) !== -1 ? "kw" : null, match[0]);
      i += match[0].length;
      continue;
    }
    /* Прочий символ — буквально (переносы/пробелы без обработки) */
    push(null, rest.charAt(0));
    i += 1;
  }
  return tokens;
}

/* Подсветка в целевой контейнер: всегда textContent (содержимое кода —
 * буквально; <script> внутри код-блока — текст без исполнения, NFR-35). */
export function highlightInto(target, code, lang) {
  target.textContent = "";
  tokenize(code, lang).forEach(function (token) {
    if (token[0] === null) {
      target.appendChild(document.createTextNode(token[1]));
    } else {
      var span = document.createElement("span");
      span.className = TOKEN_CLASSES[token[0]];
      span.textContent = token[1];
      target.appendChild(span);
    }
  });
  return target;
}

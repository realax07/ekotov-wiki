/* Самописный лексер подсветки кода P12 (design.md §5, FR-119).
 *
 * Решение — без внешних библиотек/CDN (ОГР-8): 6 языков, приоритетные
 * правила (комментарии → строки → числа → декораторы → ключевые слова →
 * функции), fail-safe «не распознал — выдал как текст».
 *
 * ReDoS-безопасность (находка F5, NFR-40): правила — sticky-regex без
 * вложенных квантификаторов и обратных ссылок; проверки, требующие
 * контекста (открывающая «(» после имени функции, закрывающая кавычка
 * строки), делаются КОДОМ поверх жадного совпадения, так что неуспех
 * правила не вызывает бэктрекинга — время линейно по длине входа;
 * вход больше MAX_HIGHLIGHT_BYTES (64 КБ) подсвечивается как plain.
 * Токены: классы tok-kw/tok-str/tok-com/tok-num/tok-fn/tok-dec над
 * ЭКРАНИРОВАННЫМ текстом (на входе — декодированный текст из textContent,
 * на выходе — безопасный HTML; §8). Потеря символов исключена: все, что
 * не совпало с правилами, эмитится как экранированный текст.
 */

var MAX_HIGHLIGHT_BYTES = 64 * 1024;

/* Экранирование текста для вставки в innerHTML. */
function esc(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* Правила языка по приоритету: {re, cls, kind}.
 * kind: 'plain' — совпало = токен; 'str' — жадное совпадение до кавычки
 * или конца строки, закрывающая кавычка проверяется кодом (чтобы
 * незакрытая строка не порождала бэктрекинг); 'fn' — имя функции,
 * «(» после (опциональных пробелов) проверяется кодом. */
var RULES = {
  python: [
    { re: /#[^\n]*/y, cls: 'com' },
    { re: /"[^"\n]*"?|'[^'\n]*'?/y, cls: 'str', kind: 'str' },
    { re: /\b\d+(?:\.\d+)?\b/y, cls: 'num' },
    { re: /@[A-Za-z_][A-Za-z0-9_.]*/y, cls: 'dec' },
    { re: /\b(?:def|class|return|for|in|if|elif|else|import|from|as|with|try|except|finally|while|lambda|None|True|False|not|and|or|is|pass|raise|global|del|yield|assert|break|continue|print)\b/y, cls: 'kw' },
    { re: /[A-Za-z_][A-Za-z0-9_]*/y, cls: 'fn', kind: 'fn' }
  ],
  js: [
    { re: /\/\/[^\n]*/y, cls: 'com' },
    { re: /\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\/?/y, cls: 'com', kind: 'str', quote: '/' },
    { re: /"[^"\n]*"?|'[^'\n]*'?|`[^`\n]*`?/y, cls: 'str', kind: 'str' },
    { re: /\b\d+(?:\.\d+)?\b/y, cls: 'num' },
    { re: /\b(?:const|let|var|function|return|for|in|of|if|else|import|from|export|default|class|extends|new|try|catch|finally|await|async|while|do|switch|case|break|continue|typeof|instanceof|null|undefined|true|false|this|throw)\b/y, cls: 'kw' },
    { re: /[A-Za-z_$][A-Za-z0-9_$]*/y, cls: 'fn', kind: 'fn' }
  ],
  bash: [
    { re: /#[^\n]*/y, cls: 'com' },
    { re: /"[^"\n]*"?|'[^'\n]*'?/y, cls: 'str', kind: 'str' },
    { re: /\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/y, cls: 'dec' },
    { re: /\b\d+\b/y, cls: 'num' },
    { re: /\b(?:if|then|else|elif|fi|for|in|while|do|done|case|esac|function|return|exit|local|export|echo|cd|set|source|sudo|apt|docker|git|curl|compose|npm|pip|python)\b/y, cls: 'kw' },
    { re: /[A-Za-z_][A-Za-z0-9_-]*/y, cls: 'fn', kind: 'fn' }
  ],
  json: [
    { re: /"(?:[^"\\\n]|\\.)*"?/y, cls: 'str', kind: 'str' },
    { re: /-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/y, cls: 'num' },
    { re: /\b(?:true|false|null)\b/y, cls: 'kw' }
  ],
  sql: [
    { re: /--[^\n]*/y, cls: 'com' },
    { re: /'[^'\n]*'?/y, cls: 'str', kind: 'str' },
    { re: /\b\d+(?:\.\d+)?\b/y, cls: 'num' },
    { re: /\b(?:select|from|where|insert|into|values|update|set|delete|create|table|drop|alter|add|join|left|right|inner|outer|on|group|by|order|having|limit|offset|and|or|not|null|primary|key|foreign|references|distinct|as|asc|desc|count|sum|avg|min|max|case|when|then|end|union|all|index|default|int|integer|varchar|text|boolean|timestamp|date)\b/iy, cls: 'kw' },
    { re: /[A-Za-z_][A-Za-z0-9_]*(?=\()/y, cls: 'fn', kind: 'fn' }
  ],
  plain: []
};

export { MAX_HIGHLIGHT_BYTES };

/* Sticky-совпадение точно с позиции i (без копий строки). */
function matchAt(rule, text, i) {
  rule.re.lastIndex = i;
  var match = rule.re.exec(text);
  if (match && match.index === i && match[0].length > 0) return match[0];
  return null;
}

/* Строка «закрыта»? Совпадение жадного скана валидно, только если оно
 * кончается закрывающим символом (иначе это незакрытая строка — плоский
 * текст; сам скан уже съеден одним совпадением — бэктрекинга нет). */
function closedString(match, quote) {
  if (match.length < 2) return false;
  var close = quote || match.charAt(0);
  return match.charAt(match.length - 1) === close;
}

/* Имя функции: после имени (плюс пробелы/табы) стоит «(». */
function followedByParen(text, end) {
  var i = end;
  while (i < text.length && (text.charAt(i) === ' ' || text.charAt(i) === '\t')) {
    i += 1;
  }
  return text.charAt(i) === '(';
}

/* Подсветка кода lang'а → безопасный HTML (экранированные спаны).
 * fail-safe: неизвестный язык, ошибка правила, переполнение 64 КБ —
 * экранированный plain без потери символов (§5, NFR-39/40). */
export function highlight(code, lang) {
  var text = String(code == null ? '' : code);
  if (text.length > MAX_HIGHLIGHT_BYTES) {
    return esc(text); // крупный листинг — plain (§5)
  }
  var rules = RULES[lang];
  if (!rules || rules.length === 0) {
    return esc(text);
  }
  try {
    /* Один проход по тексту: в каждой позиции правила по приоритету
     * (sticky-regex); смещение двигается минимум на 1 символ, каждый
     * символ посещается O(1) раз — линейно (F5). */
    var out = [];
    var pos = 0;
    while (pos < text.length) {
      var value = null;
      var cls = '';
      var hit = null;
      for (var r = 0; r < rules.length; r += 1) {
        var found = matchAt(rules[r], text, pos);
        if (found !== null) {
          hit = rules[r];
          value = found;
          break;
        }
      }
      if (value === null) {
        /* Плоский текст: пачка символов до следующего старта правила. */
        var next = pos + 1;
        while (next < text.length && !startsRule(rules, text, next)) {
          next += 1;
        }
        out.push(esc(text.slice(pos, next)));
        pos = next;
        continue;
      }
      if (hit.kind === 'str' && !closedString(value, hit.quote)) {
        /* Незакрытая строка — кавычка плоским текстом, скан не откатываем. */
        out.push(esc(value.charAt(0)));
        pos += 1;
        continue;
      }
      if (hit.kind === 'fn' && !followedByParen(text, pos + value.length)) {
        /* Не функция — имя плоским текстом (целиком, без почтовой
         * перепроверки посимвольно — линейно). */
        out.push(esc(value));
        pos += value.length;
        continue;
      }
      out.push('<span class="tok-' + hit.cls + '">' + esc(value) + '</span>');
      pos += value.length;
    }
    return out.join('');
  } catch (err) {
    return esc(text); // любая ошибка лексера — plain текст (§5)
  }
}

/* Начинается ли какое-либо правило точно с позиции i. */
function startsRule(rules, text, i) {
  for (var r = 0; r < rules.length; r += 1) {
    if (matchAt(rules[r], text, i) !== null) return true;
  }
  return false;
}

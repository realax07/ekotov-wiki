/* Поиск по разделу Wiki (tasks.md 3.1 add-wiki; FR-114, design §6–§7).
 * Рендер выдачи СТРОГО по утвержденному мокапу design/wiki-tree.html:
 *   ul.wiki-results > li > a.result-item
 *     div.result-title, div.result-path, div.result-snippet > mark.
 *
 * GET /api/wiki/search?q=; фрагмент с подсветкой собирается ПО ОФФСЕТУ из
 * ответа (match_offset/match_length) через documentFragment + textContent —
 * HTML из ответа в DOM не вставляется (санитизация на клиенте не нужна,
 * паттерн board/search). Пустой q — сервер 422; пустой результат —
 * «ничего не найдено» по мокапу. Дебаунс 300 мс (NFR-30). Данные
 * пользователя — только createElement + textContent. 401 → /login.
 * Без внешних зависимостей (ОГР-8).
 */

const DEBOUNCE_MS = 300;
const SNIPPET_CONTEXT = 30; // символов контекста вокруг совпадения в DOM

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/* Фрагмент с <mark> по оффсету (design §6): сниппет из ответа — плоский
 * текст (сервер не отдает HTML); разметку совпадения строим здесь. */
export function buildSnippet(snippet, matchOffset, matchLength) {
  const fragment = document.createDocumentFragment();
  if (matchOffset < 0 || matchLength <= 0) {
    fragment.appendChild(document.createTextNode(snippet));
    return fragment;
  }
  const start = Math.max(0, matchOffset - SNIPPET_CONTEXT);
  const end = Math.min(snippet.length, matchOffset + matchLength + SNIPPET_CONTEXT);
  const cut = (s) => (s.length > 0 && start > 0 ? `…${s}` : s);

  if (start > 0) fragment.appendChild(document.createTextNode('…'));
  if (matchOffset > start) {
    fragment.appendChild(document.createTextNode(snippet.slice(start, matchOffset)));
  }
  fragment.appendChild(el('mark', null, snippet.slice(matchOffset, matchOffset + matchLength)));
  if (end > matchOffset + matchLength) {
    fragment.appendChild(document.createTextNode(snippet.slice(matchOffset + matchLength, end)));
  }
  if (end < snippet.length) fragment.appendChild(document.createTextNode('…'));
  return fragment;
}

function renderResultItem(result) {
  const li = el('li');
  const link = el('a', 'result-item');
  link.href = `/wiki/${result.id}`;

  link.appendChild(el('div', 'result-title', result.title));
  if (result.path) link.appendChild(el('div', 'result-path', result.path));
  const snippet = el('div', 'result-snippet');
  snippet.appendChild(buildSnippet(result.snippet, result.match_offset, result.match_length));
  link.appendChild(snippet);

  li.appendChild(link);
  return li;
}

function renderEmptyResults(container) {
  container.replaceChildren(
    el('p', 'wiki-empty wiki-no-results', 'Ничего не найдено')
  );
}

export async function runWikiSearch(container, query) {
  const url = `/api/wiki/search?q=${encodeURIComponent(query)}`;
  const response = await fetch(url, { credentials: 'same-origin' });
  if (response.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (response.status === 422 || !response.ok) {
    renderEmptyResults(container);
    return;
  }
  const data = await response.json();
  const results = data.results ?? [];

  if (results.length === 0) {
    renderEmptyResults(container);
    return;
  }

  const ul = el('ul', 'wiki-results');
  ul.setAttribute('aria-label', 'Результаты поиска по разделу Wiki');
  for (const result of results) ul.appendChild(renderResultItem(result));
  container.replaceChildren(ul);
}

export function initWikiSearch() {
  const input = document.querySelector('#wiki-search');
  const container = document.querySelector('#wiki-search-results');
  const counter = document.querySelector('.filter-count');
  if (!input || !container) return null;

  let timer = null;
  let controller = null;

  const refresh = async () => {
    const query = input.value.trim();
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (controller) controller.abort();
    controller = new AbortController();

    if (query.length === 0) {
      container.replaceChildren();
      if (counter) counter.textContent = '';
      return;
    }

    try {
      await runWikiSearch(container, query);
      const count = container.querySelectorAll('.result-item').length;
      if (counter) counter.textContent = `Найдено: ${count}`;
    } catch (error) {
      if (error.name !== 'AbortError') throw error;
    }
  };

  input.addEventListener('input', () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(refresh, DEBOUNCE_MS);
  });

  return { refresh };
}

/* Автозапуск ES-модуля (подключение — <script type="module"> в wiki.html). */
initWikiSearch();

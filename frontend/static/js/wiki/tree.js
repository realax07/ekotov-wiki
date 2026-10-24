/* Дерево страниц Wiki (tasks.md 3.1 add-wiki; FR-107, design §6–§7).
 * Рендер СТРОГО по утвержденному мокапу design/wiki-tree.html:
 *   ul.wiki-tree > li.tree-node > div.tree-row
 *     [button.tree-toggle aria-expanded] | [span.tree-spacer (лист)]
 *     a.tree-link → /wiki/{id} (title = полное название — подсказка
 *     при обрезке ellipsis; meta-счетчик снят — возврат приемки)
 *   вложенные ul.tree-children (скрытие — атрибут hidden).
 *
 * Плоский список GET /api/wiki/pages → вложенность по parent_id за ОДИН
 * запрос (O(n), NFR-30); раскрытие/сворачивание — в cookie wiki_tree_expanded
 * (возврат живой приемки 2026-10-11: дефолт — ВСЕ СВЕРНУТО, раскрытые id —
 * JSON-массив в cookie на 24 часа, после перехода на статью состояние
 * восстанавливается). DOM — только createElement +
 * textContent (данные пользователя в разметку не вставляются, паттерн
 * board/search). 401 при протухшей сессии → редирект на /login.
 * Без внешних зависимостей (ОГР-8).
 */

const CHEVRON_SVG =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const PLUS_SVG =
  '<svg class="btn-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setChildren(node, children) {
  for (const child of children) node.appendChild(child);
}

/* Плоский список → {id: children[]} одним проходом (design §6, O(n)). */
export function buildTree(pages) {
  const byParent = new Map();
  for (const page of pages) {
    const key = page.parent_id == null ? null : page.parent_id;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key).push(page);
  }
  return byParent;
}

/* meta-счетчик («N страниц · обновлено …») снят — возврат живой приемки
   p15-wiki-5: в узкой колонке он вытеснял название за пределы плитки.
   formatDate/descendantCount/metaText удалены за ненадобностью. */

/* Состояние раскрытия дерева — cookie wiki_tree_expanded (возврат живой
   приемки 2026-10-11, приказ Заказчика): значение — JSON-массив id страниц
   в раскрытом состоянии, path=/, max-age=86400 (24 часа), SameSite=Lax.
   Дефолт (нет/битая cookie) — ВСЕ узлы СВЕРНУТЫ. */
const TREE_COOKIE_NAME = 'wiki_tree_expanded';
const TREE_COOKIE_MAX_AGE = 86400; // 24 часа

function readExpandedIds() {
  const prefix = TREE_COOKIE_NAME + '=';
  for (const piece of document.cookie.split(';')) {
    const part = piece.trim();
    if (part.startsWith(prefix)) {
      try {
        const parsed = JSON.parse(decodeURIComponent(part.slice(prefix.length)));
        if (Array.isArray(parsed)) {
          return new Set(parsed.map((id) => String(id)));
        }
      } catch (err) {
        /* битая cookie — дефолт: все свернуто */
      }
      break;
    }
  }
  return new Set();
}

function writeExpandedIds(idsSet) {
  const value = encodeURIComponent(JSON.stringify([...idsSet]));
  document.cookie =
    `${TREE_COOKIE_NAME}=${value}; path=/; max-age=${TREE_COOKIE_MAX_AGE}; ` +
    'SameSite=Lax';
}

function makeToggle(page, childrenUl, expandedIds) {
  const toggle = el('button', 'tree-toggle');
  toggle.type = 'button';
  const expanded = expandedIds.has(String(page.id));
  toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
  childrenUl.hidden = !expanded;
  toggle.innerHTML = CHEVRON_SVG; // статический SVG из мокапа, не данные
  const label = page.title;
  toggle.setAttribute(
    'aria-label',
    `${expanded ? 'Свернуть' : 'Развернуть'} раздел «${label}»`
  );
  toggle.addEventListener('click', () => {
    const nowExpanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', nowExpanded ? 'false' : 'true');
    toggle.setAttribute(
      'aria-label',
      `${nowExpanded ? 'Развернуть' : 'Свернуть'} раздел «${label}»`
    );
    childrenUl.hidden = nowExpanded;
    /* состояние — в cookie (24ч), переживает переход на статью и назад */
    const ids = readExpandedIds();
    if (nowExpanded) {
      ids.delete(String(page.id));
    } else {
      ids.add(String(page.id));
    }
    writeExpandedIds(ids);
  });
  return toggle;
}

function renderNode(page, byParent, expandedIds) {
  const li = el('li', 'tree-node');
  const row = el('div', 'tree-row');
  const children = byParent.get(page.id) ?? [];

  if (children.length > 0) {
    const childrenUl = el('ul', 'tree-children');
    for (const child of children) {
      childrenUl.appendChild(renderNode(child, byParent, expandedIds));
    }
    row.appendChild(makeToggle(page, childrenUl, expandedIds));
    setChildren(row, [makeLink(page)]);
    li.appendChild(row);
    li.appendChild(childrenUl);
  } else {
    setChildren(row, [el('span', 'tree-spacer'), makeLink(page)]);
    li.appendChild(row);
  }
  return li;
}

function makeLink(page) {
  const link = el('a', 'tree-link', page.title);
  link.href = `/wiki/${page.id}`;
  // Полное название в подсказке (возврат живой приемки): длинные заголовки
  // режутся ellipsis в узкой колонке — title показывает целиком.
  link.title = page.title;
  return link;
}

/* Пустое состояние по мокапу (wiki-tree.html демо-зона): dashed-плашка
 * + кнопка «Создать первую страницу» → редактор (?create=1, задача 3.3). */
export function renderEmptyState(container) {
  const empty = el('div', 'wiki-empty');
  setChildren(empty, [
    el('h2', null, 'В Wiki пока нет страниц'),
    el('p', null, 'Создайте первую страницу — она станет корнем дерева раздела.'),
  ]);
  const button = el('button', 'wiki-create');
  button.type = 'button';
  button.innerHTML = PLUS_SVG;
  button.appendChild(document.createTextNode('Создать первую страницу'));
  button.setAttribute('aria-label', 'Создать первую страницу');
  button.addEventListener('click', () => {
    window.location.href = '/wiki?create=1';
  });
  empty.appendChild(button);
  container.appendChild(empty);
  return empty;
}

export async function initWikiTree() {
  const container = document.querySelector('aside.wiki-tree');
  if (!container) return null;

  const response = await fetch('/api/wiki/pages', { credentials: 'same-origin' });
  if (response.status === 401) {
    window.location.href = '/login';
    return null;
  }
  if (!response.ok) {
    container.appendChild(el('p', 'wiki-error', 'Не удалось загрузить дерево страниц'));
    return null;
  }

  const data = await response.json();
  const pages = data.pages ?? [];
  container.textContent = '';

  if (pages.length === 0) {
    return renderEmptyState(container);
  }

  const byParent = buildTree(pages);
  const expandedIds = readExpandedIds();
  const tree = el('ul', 'wiki-tree');
  tree.setAttribute('aria-label', 'Дерево страниц Wiki');

  const roots = byParent.get(null) ?? [];
  for (const page of roots) tree.appendChild(renderNode(page, byParent, expandedIds));

  /* redesign-console 2.3 (decor, design §D2): текущая страница — янтарная
   * подсветка узла дерева (aria-current="page"; вид дает CSS — подложка
   * --p-amber-900 + текст --p-amber-400). id страницы — из data-page-id
   * контейнера .wiki-layout (ставит роутер pages.py). */
  const layout = document.querySelector('.wiki-layout[data-page-id]');
  if (layout) {
    const currentId = layout.dataset.pageId;
    const currentLink = tree.querySelector(`a.tree-link[href="/wiki/${currentId}"]`);
    if (currentLink) currentLink.setAttribute('aria-current', 'page');
  }

  container.appendChild(tree);
  return tree;
}

/* Тулбарная «Создать страницу» (wiki.html) → редактор (?create=1, 3.3):
 * слушатель здесь, т.к. tree.js — единственный модуль, живущий на /wiki
 * вне зависимости от режима просмотра.
 * Возврат живой приемки 2026-10-11: на странице статьи /wiki/{id} кнопка
 * ведет в редактор с ПРЕДВЫБРАННЫМ РОДИТЕЛЕМ = текущая страница
 * (?create=1&parent={id}, state.parentPreselect editor.js); на списке /wiki —
 * без parent, как раньше. */
function currentArticleId() {
  const layout = document.querySelector('.wiki-layout');
  if (layout && layout.dataset && /^\d+$/.test(String(layout.dataset.pageId || ''))) {
    return String(layout.dataset.pageId);
  }
  const match = window.location.pathname.match(/^\/wiki\/(\d+)$/);
  return match ? match[1] : null;
}

function bindToolbarCreate() {
  const toolbarButton = document.querySelector('.wiki-toolbar .wiki-create');
  if (toolbarButton) {
    toolbarButton.addEventListener('click', () => {
      const pageId = currentArticleId();
      window.location.href = pageId
        ? `/wiki?create=1&parent=${pageId}`
        : '/wiki?create=1';
    });
  }
}

bindToolbarCreate();

initWikiTree();

/* Дерево страниц Wiki (tasks.md 3.1 add-wiki; FR-107, design §6–§7).
 * Рендер СТРОГО по утвержденному мокапу design/wiki-tree.html:
 *   ul.wiki-tree > li.tree-node > div.tree-row
 *     [button.tree-toggle aria-expanded] | [span.tree-spacer (лист)]
 *     a.tree-link → /wiki/{id}, span.tree-meta
 *   вложенные ul.tree-children (скрытие — атрибут hidden).
 *
 * Плоский список GET /api/wiki/pages → вложенность по parent_id за ОДИН
 * запрос (O(n), NFR-30); раскрытие/сворачивание — в памяти страницы,
 * без сохранения на сервер (design §6). DOM — только createElement +
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

function formatDate(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function descendantCount(byParent, pageId) {
  let total = 0;
  const queue = [...(byParent.get(pageId) ?? [])];
  while (queue.length > 0) {
    const node = queue.shift();
    total += 1;
    queue.push(...(byParent.get(node.id) ?? []));
  }
  return total;
}

/* Счетчик meta по мокапу: «N страниц · обновлено {дата}» (узел с детьми,
   DV-3 review-001) либо дата (лист). */
function metaText(byParent, page) {
  const direct = (byParent.get(page.id) ?? []).length;
  if (direct > 0) {
    const total = descendantCount(byParent, page.id);
    const label = total === 1 ? 'страница' : total < 5 ? 'страницы' : 'страниц';
    const updated = formatDate(page.updated_at);
    return updated ? `${total} ${label} · обновлено ${updated}` : `${total} ${label}`;
  }
  return formatDate(page.updated_at);
}

function makeToggle(page, childrenUl) {
  const toggle = el('button', 'tree-toggle');
  toggle.type = 'button';
  toggle.setAttribute('aria-expanded', 'true');
  toggle.innerHTML = CHEVRON_SVG; // статический SVG из мокапа, не данные
  const label = page.title;
  toggle.addEventListener('click', () => {
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
    toggle.setAttribute(
      'aria-label',
      `${expanded ? 'Развернуть' : 'Свернуть'} раздел «${label}»`
    );
    childrenUl.hidden = expanded;
  });
  toggle.setAttribute('aria-label', `Свернуть раздел «${label}»`);
  return toggle;
}

function renderNode(page, byParent) {
  const li = el('li', 'tree-node');
  const row = el('div', 'tree-row');
  const children = byParent.get(page.id) ?? [];

  if (children.length > 0) {
    const childrenUl = el('ul', 'tree-children');
    for (const child of children) childrenUl.appendChild(renderNode(child, byParent));
    row.appendChild(makeToggle(page, childrenUl));
    setChildren(row, [
      makeLink(page),
      el('span', 'tree-meta', metaText(byParent, page)),
    ]);
    li.appendChild(row);
    li.appendChild(childrenUl);
  } else {
    setChildren(row, [
      el('span', 'tree-spacer'),
      makeLink(page),
      el('span', 'tree-meta', metaText(byParent, page)),
    ]);
    li.appendChild(row);
  }
  return li;
}

function makeLink(page) {
  const link = el('a', 'tree-link', page.title);
  link.href = `/wiki/${page.id}`;
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
  const tree = el('ul', 'wiki-tree');
  tree.setAttribute('aria-label', 'Дерево страниц Wiki');

  const roots = byParent.get(null) ?? [];
  for (const page of roots) tree.appendChild(renderNode(page, byParent));

  container.appendChild(tree);
  return tree;
}

/* Тулбарная «Создать страницу» (wiki.html) → редактор (?create=1, 3.3):
 * слушатель здесь, т.к. tree.js — единственный модуль, живущий на /wiki
 * вне зависимости от режима просмотра. */
function bindToolbarCreate() {
  const toolbarButton = document.querySelector('.wiki-toolbar .wiki-create');
  if (toolbarButton) {
    toolbarButton.addEventListener('click', () => {
      window.location.href = '/wiki?create=1';
    });
  }
}

bindToolbarCreate();

initWikiTree();

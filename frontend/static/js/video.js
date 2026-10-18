/* Страница «Видео» — tasks.md 1.5 + 2.4 + 3.1/3.2 фронт video-hosting
 * (куски A, D, B).
 *
 * Вид — по утвержденным мокапам (design/video-hosting/video-list.html,
 * video-upload.html, video-view.html); селекторы — дословно из макетов.
 * Кусок B (волна 3): бейджи статусов конвертации («загружено»/
 * «конвертируется» — пульсирующий индикатор, aria-busy; «готово»;
 * «ошибка» — подсказка «оригинал сохранен»), convert-note в форме
 * загрузки (ревью-001 п.2), автообновление списка polling'ом (3 c),
 * пока есть незавершенные конвертации; статус открытого просмотра
 * обновляется без перезагрузки (плейсхолдер → плеер).
 * Кусок D: реакции (лайк/дизлайк — ровно один голос: повторный клик
 * снимает, клик по второй переносит), комментарии (удаление — только
 * своих: comment.user_id === me.id), категории (общий справочник
 * с «Галереей»: выбор при загрузке, «+ Новая категория…» через POST
 * /api/categories ядра, фильтр в списке).
 * Кусок C (4.1): поиск по подстроке имени (#video-search, debounce,
 * регистр не учитывается — сервер), сортировка по имени (#video-sort,
 * asc по мокапу — «Имя А→Я»), «Сбросить» (#video-filter-reset —
 * поиск+категория к дефолту); параметры комбинируются в один запрос
 * ?query=&order=&category= и сохраняются при polling-обновлении списка;
 * пустой результат фильтра — отдельный тихий state (#video-search-empty).
 * Волна 7 (7.2): переименование видео на странице просмотра по образцу
 * rename изображений (FR-97, gallery.js): edit-иконка у имени
 * (#player-rename), инлайн-поле (#player-rename-field), Enter/✓ —
 * сохранить, Esc — отмена; PATCH {title} на /api/videos/{id}; имя
 * обновляется в DOM (просмотр + карточка списка) БЕЗ перезагрузки,
 * новое имя переживает перезагрузку (сервер); ошибки 422/404 — строка
 * (#player-rename-error).
 *
 * Данные — API video-сервиса (за сессией, NFR-36/38):
 *   GET    /api/videos                       — список (+ ?category=<id|none>
 *                                              &query=<подстрока>&order=asc|desc);
 *   POST   /api/videos                       — загрузка multipart (≤ 500 МБ,
 *                                              опц. category_id);
 *   DELETE /api/videos/{id}                  — удаление;
 *   PATCH  /api/videos/{id}                  — {title} переименование
 *                                              (волна 7; паритет FR-97);
 *   GET    /api/videos/{id}/preview          — кадр (409 = плейсхолдер);
 *   GET    /api/videos/{id}/comments         — комментарии;
 *   POST   /api/videos/{id}/comments         — {text} добавить;
 *   DELETE /api/videos/{id}/comments/{cid}   — удалить СВОЙ (чужой = 403);
 *   PUT    /api/videos/{id}/reaction         — {value: 1|-1} голос;
 *   GET    /api/videos/categories            — справочник (RO);
 *   GET    /api/auth/me                      — кто я (id для «свой/чужой»);
 *   POST   /api/categories                   — новая категория (ядро, галерея).
 * Файл для плеера — file_url из списка (nginx /videos/<id>/…, design §5).
 * Статусы: uploaded «загружено» / converting «конвертируется» /
 * ready «готово» / error «ошибка»; плеер — ТОЛЬКО для «готово»
 * (Scenario «Не готовое видео не проигрывается»).
 *
 * XSS-дисциплина (ОГР-11, паритет gallery.js): рендер пользовательских
 * данных — createElement + textContent; innerHTML — только статические
 * inline-SVG иконки.
 */

const LIMIT_BYTES = 500 * 1024 * 1024; // ОВ-1: до 500 МБ включительно

const STATUS_LABELS = {
  uploaded: 'загружено',
  converting: 'конвертируется',
  ready: 'готово',
  error: 'ошибка',
};

const views = ['video-list-view', 'video-upload-view', 'video-player-view'];

/* Кусок D: текущий пользователь (id — рендер «удалить» у своих) и
 * справочник категорий (общий с галереей). Кусок C: query — подстрока
 * поиска (trim, пустая = все), order — сортировка по имени («Имя А→Я»
 * по мокапу — дефолт). */
const state = { me: null, categories: [], activeCategory: '', query: '', order: 'asc' };

/* Кусок C: параметры списка одним куском — loadList и polling-тик
 * (refreshTick) ходят с ОДНИМИ И ТЕМИ ЖЕ фильтрами (поиск/сортировка
 * не сбрасываются автообновлением куска B). */
function buildListParams() {
  const params = new URLSearchParams();
  if (state.activeCategory) params.set('category', state.activeCategory);
  if (state.query) params.set('query', state.query);
  if (state.order) params.set('order', state.order);
  const qs = params.toString();
  return qs ? '?' + qs : '';
}

/* Кусок B: статусы «загружено»/«конвертируется» — не финальные, список
 * обновляется опросом (polling; SSE спекой не предусмотрена), пока есть
 * незавершенные записи (design §3; сценарий «статусы без перезагрузки»). */
const PENDING_STATUSES = ['uploaded', 'converting'];
const REFRESH_INTERVAL_MS = 3000;
let refreshTimer = null;

function showView(id) {
  for (const v of views) {
    document.getElementById(v).hidden = v !== id;
  }
  window.scrollTo(0, 0);
}

function fmtSize(bytes) {
  const mb = bytes / (1024 * 1024);
  if (mb >= 1) {
    return (mb >= 100 ? Math.round(mb) : Math.round(mb * 10) / 10) + ' МБ';
  }
  return Math.max(1, Math.round(bytes / 1024)) + ' КБ';
}

function fmtDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function fmtExt(filename) {
  const parts = String(filename || '').split('.');
  return parts.length > 1 ? parts[parts.length - 1] : 'bin';
}

function statusBadge(status) {
  const label = STATUS_LABELS[status] || status;
  const span = document.createElement('span');
  span.className = 'status-badge status-' + status;
  if (status === 'converting') {
    // Индикатор конвертации (мокап video-list.html): точка пульсирует
    // CSS-анимацией, для ассистивных технологий — aria-busy.
    span.setAttribute('aria-busy', 'true');
  }
  const dot = document.createElement('span');
  dot.className = 'status-dot';
  span.append(dot, document.createTextNode(label));
  return span;
}

/* ===== Список (мокап video-list.html) ===== */

function buildCard(item) {
  const card = document.createElement('a');
  card.href = '#';
  card.className = 'v-card';
  card.dataset.videoId = item.id;
  card.setAttribute(
    'aria-label',
    `${item.filename} (${item.status === 'ready' ? 'готово' : STATUS_LABELS[item.status] || item.status}) — открыть карточку`
  );

  const thumb = document.createElement('div');
  thumb.className = 'v-thumb';
  thumb.setAttribute('aria-hidden', 'true');

  const fmt = document.createElement('span');
  fmt.className = 'fmt-badge';
  fmt.textContent = fmtExt(item.filename);

  if (item.status === 'ready') {
    // Кадр отдаст preview-эндпоинт (в куске A кадра еще нет — 409 →
    // плейсхолдер ph-frame по макету; кусок B положит preview.jpg).
    const img = document.createElement('img');
    img.alt = '';
    img.src = item.preview_url;
    img.addEventListener('error', () => {
      img.remove();
      const ph = document.createElement('div');
      ph.className = 'ph-frame';
      thumb.prepend(ph);
    });
    thumb.append(img);
    const play = document.createElement('span');
    play.className = 'play-overlay';
    play.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5l11 6.5-11 6.5v-13z" fill="currentColor"/></svg>';
    thumb.append(play);
  } else {
    const ph = document.createElement('div');
    ph.className = 'ph-no-frame';
    ph.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 9.2l5 2.8-5 2.8V9.2z" fill="currentColor"/></svg>';
    ph.append(document.createTextNode('превью появится после конвертации'));
    thumb.append(ph);
  }
  thumb.append(fmt);

  const body = document.createElement('div');
  body.className = 'v-card-body';
  const title = document.createElement('h3');
  title.className = 'v-card-title';
  title.textContent = item.filename;
  const meta = document.createElement('div');
  meta.className = 'v-card-meta';
  meta.append(statusBadge(item.status));
  if (item.category_name) {
    const pill = document.createElement('span');
    pill.className = 'task-category';
    pill.textContent = item.category_name; // пилюля категории (мокап video-list.html)
    meta.append(pill);
  }
  const size = document.createElement('span');
  size.textContent = fmtSize(item.size_bytes);
  const date = document.createElement('span');
  date.textContent = '· ' + fmtDate(item.created_at);
  meta.append(size, date);
  if (item.status === 'error') {
    // Кусок B: подсказка при ошибке конвертации (оригинал сохранен —
    // файл можно удалить или перезалить; Requirement «Удаление оригинала…»).
    const hint = document.createElement('span');
    hint.className = 'error-hint';
    hint.textContent = 'конвертация не удалась — оригинал сохранен';
    meta.append(hint);
  }
  body.append(title, meta);

  card.append(thumb, body);
  card.addEventListener('click', (e) => {
    e.preventDefault();
    openPlayer(item);
  });
  return card;
}

function hasActiveFilters() {
  return Boolean(state.activeCategory || state.query);
}

/* Общая отрисовка списка для loadList и polling-тика (кусок B): карточки,
 * счетчик, пустые state'ы (библиотека пуста vs ничего не найдено по
 * фильтрам — кусок C, мокап video-list.html). */
function renderList(videos) {
  const grid = document.getElementById('video-grid');
  grid.querySelectorAll('.v-card').forEach((el) => el.remove());
  for (const item of videos) {
    grid.append(buildCard(item));
  }
  document.getElementById('video-count').textContent = 'Видео: ' + videos.length;
  const filtered = hasActiveFilters();
  document.getElementById('video-empty').hidden = filtered || videos.length > 0;
  document.getElementById('video-search-empty').hidden = !filtered || videos.length > 0;
}

async function loadList() {
  // Кусок C: query/order комбинируются с фильтром категории (кусок D).
  const resp = await fetch('/api/videos' + buildListParams());
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  const data = await resp.json();
  const videos = data.videos || [];
  state.listItems = videos;
  renderList(videos);
  // Кусок B: пока есть незавершенные конвертации — автообновление списка.
  scheduleListRefresh(videos);
}

/* ===== Кусок B: автообновление списка (polling, design §3) ===== */

function hasPending(items) {
  return items.some((item) => PENDING_STATUSES.includes(item.status));
}

function scheduleListRefresh(items) {
  if (!hasPending(items)) {
    stopListRefresh();
    return;
  }
  if (refreshTimer !== null) return;
  refreshTimer = setInterval(refreshTick, REFRESH_INTERVAL_MS);
}

function stopListRefresh() {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

async function refreshTick() {
  // Кусок C: polling ходит с теми же query/order/category, что и loadList.
  const resp = await fetch('/api/videos' + buildListParams());
  if (!resp.ok) return; // сеть/сервис моргнули — следующий тик повторит
  const data = await resp.json();
  const videos = data.videos || [];
  state.listItems = videos;
  renderList(videos);
  scheduleListRefresh(videos);
  // Открыт просмотр: статус открытого видео изменился — перерисовать
  // (например, «конвертируется» → «готово»: плейсхолдер сменяется плеером).
  const playerView = document.getElementById('video-player-view');
  if (currentPlayerId && !playerView.hidden) {
    const item = videos.find((entry) => entry.id === currentPlayerId);
    if (item && item.status !== state.playerStatus) openPlayer(item);
  }
}

/* ===== Категории (кусок D: общий справочник с «Галереей») ===== */

async function loadCategories() {
  const resp = await fetch('/api/videos/categories');
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  const data = await resp.json();
  state.categories = data.categories || [];
  fillCategorySelects();
}

function fillCategorySelects() {
  // Фильтр списка (мокап video-list.html): «Все категории» + справочник +
  // «Без категории» (значение none = category_id IS NULL).
  const filter = document.getElementById('video-category');
  const filterValue = filter.value;
  filter.textContent = '';
  const all = document.createElement('option');
  all.value = '';
  all.textContent = 'Все категории';
  filter.append(all);
  for (const cat of state.categories) {
    const opt = document.createElement('option');
    opt.value = String(cat.id);
    opt.textContent = cat.name;
    filter.append(opt);
  }
  const none = document.createElement('option');
  none.value = 'none';
  none.textContent = 'Без категории';
  filter.append(none);
  filter.value = filterValue;

  // Форма загрузки (мокап video-upload.html): «Без категории» и опция
  // «+ Новая категория…» стоят в шаблоне — справочник вставляется между.
  const upload = document.getElementById('up-category');
  const uploadValue = upload.value;
  upload.querySelectorAll('option[data-src="api"]').forEach((el) => el.remove());
  const newOption = upload.querySelector('option[value="new"]');
  for (const cat of state.categories) {
    const opt = document.createElement('option');
    opt.dataset.src = 'api';
    opt.value = String(cat.id);
    opt.textContent = cat.name;
    upload.insertBefore(opt, newOption);
  }
  upload.value = uploadValue === 'new' ? 'new' : uploadValue;
}

/* ===== Просмотр (мокап video-view.html) ===== */

let currentPlayerId = null;

function renderReactionButtons(reaction) {
  const my = reaction.my_reaction;
  const likeBtn = document.getElementById('like-button');
  const dislikeBtn = document.getElementById('dislike-button');
  document.getElementById('like-count').textContent = String(reaction.likes);
  document.getElementById('dislike-count').textContent = String(reaction.dislikes);
  likeBtn.classList.toggle('my-vote', my === 1);
  dislikeBtn.classList.toggle('my-vote', my === -1);
  likeBtn.setAttribute('aria-pressed', my === 1 ? 'true' : 'false');
  dislikeBtn.setAttribute('aria-pressed', my === -1 ? 'true' : 'false');
  likeBtn.setAttribute(
    'aria-label',
    my === 1 ? 'Нравится, ваш голос учтен. Снять голос' : 'Нравится. Поставить голос'
  );
  dislikeBtn.setAttribute(
    'aria-label',
    my === -1 ? 'Не нравится, ваш голос учтен. Снять голос' : 'Не нравится. Поставить голос'
  );
  const hint = document.getElementById('react-hint');
  if (my === 1 || my === -1) {
    hint.textContent =
      'ваш голос — «' + (my === 1 ? 'Нравится' : 'Не нравится') + '» (повторный клик снимет)';
    hint.hidden = false;
  } else {
    hint.textContent = '';
    hint.hidden = true;
  }
}

async function sendReaction(value) {
  if (!currentPlayerId) return;
  const resp = await fetch('/api/videos/' + currentPlayerId + '/reaction', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (!resp.ok) return;
  renderReactionButtons(await resp.json());
}

/* ===== Комментарии (кусок D, мокап video-view.html .comments-card) ===== */

function isMyComment(comment) {
  // Прямое сравнение по me.id (паритет gallery.js: id из /api/auth/me).
  return (
    Boolean(state.me && state.me.id != null) &&
    Number(comment.user_id) === Number(state.me.id)
  );
}

function renderComments(comments) {
  const list = document.getElementById('comments-list');
  list.textContent = '';
  for (const comment of comments) {
    const item = document.createElement('div');
    item.className = 'comment';

    const head = document.createElement('div');
    head.className = 'comment-head';
    const author = document.createElement('span');
    author.className = 'comment-author';
    author.textContent = comment.user;
    const when = document.createElement('span');
    when.textContent = fmtDate(comment.created_at);
    head.append(author, when);
    if (isMyComment(comment)) {
      // «удалить» — только у СВОИХ (у чужого кнопки нет; API = 403).
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'comment-delete';
      del.setAttribute('aria-label', 'Удалить свой комментарий');
      del.textContent = 'удалить';
      del.addEventListener('click', () => deleteComment(comment.id));
      head.append(del);
    }

    const body = document.createElement('p');
    body.className = 'comment-body';
    body.textContent = comment.text;

    item.append(head, body);
    list.append(item);
  }
  document.getElementById('comment-count').textContent = '(' + comments.length + ')';
  document.getElementById('comments-empty').hidden = comments.length > 0;
}

async function loadComments() {
  if (!currentPlayerId) return;
  const resp = await fetch('/api/videos/' + currentPlayerId + '/comments');
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (!resp.ok) return;
  const data = await resp.json();
  renderComments(data.comments || []);
}

async function deleteComment(commentId) {
  if (!currentPlayerId) return;
  const resp = await fetch(
    '/api/videos/' + currentPlayerId + '/comments/' + commentId,
    { method: 'DELETE' }
  );
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (resp.ok || resp.status === 404) loadComments();
}

async function submitComment() {
  if (!currentPlayerId) return;
  const input = document.getElementById('video-comment-input');
  const text = input.value.trim();
  if (!text) return;
  const resp = await fetch('/api/videos/' + currentPlayerId + '/comments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (resp.status === 201) {
    input.value = '';
    document.getElementById('comment-send-button').disabled = true;
    loadComments();
  }
}

function openPlayer(item) {
  currentPlayerId = item.id;
  state.playerStatus = item.status;
  document.getElementById('player-title').textContent = item.filename;
  // Волна 7: редактор имени сбрасывается при открытии/переключении видео.
  closeRenameEditor();

  const card = document.getElementById('player-card');
  card.innerHTML = '';
  if (item.status === 'ready') {
    // Нативный <video>; файл — nginx-отдача из тома (Range для прогрессивной
    // отдачи faststart-mp4). Плеер запускается ТОЛЬКО для «готово».
    const video = document.createElement('video');
    video.controls = true;
    video.preload = 'metadata';
    video.setAttribute('aria-label', 'Видео «' + item.filename + '»');
    video.src = item.file_url;
    card.append(video);
  } else {
    // Scenario «Не готовое видео не проигрывается»: плейсхолдер со статусом.
    const pending = document.createElement('div');
    pending.className = 'player-pending';
    pending.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M10 9.2l5 2.8-5 2.8V9.2z" fill="currentColor"/></svg>';
    pending.append(statusBadge(item.status));
    if (item.status === 'error') {
      const hint = document.createElement('span');
      hint.className = 'error-hint';
      hint.textContent = 'конвертация не удалась — оригинал сохранен';
      pending.append(hint);
    }
    card.append(pending);
  }

  const statusCell = document.getElementById('player-status');
  statusCell.innerHTML = '';
  statusCell.append(statusBadge(item.status));

  // Пилюля категории (мокап video-view.html: dd .task-category).
  const catCell = document.getElementById('player-category');
  catCell.innerHTML = '';
  const pill = document.createElement('span');
  pill.className = 'task-category' + (item.category_name ? '' : ' task-category-none');
  pill.textContent = item.category_name || 'Без категории';
  catCell.append(pill);

  document.getElementById('player-size').textContent = fmtSize(item.size_bytes);
  document.getElementById('player-date').textContent = fmtDate(item.created_at);

  // Кусок D: реакции — из агрегатов списка (my_reaction/likes/dislikes);
  // комментарии — отдельным запросом.
  renderReactionButtons({
    my_reaction: item.my_reaction,
    likes: item.likes,
    dislikes: item.dislikes,
  });
  loadComments();

  showView('video-player-view');
}

/* ===== Переименование видео (волна 7, tasks 7.2; образец — rename
   лайтбокса галереи FR-97, gallery.js bindRename/submitRename) ===== */

function currentVideo() {
  if (!currentPlayerId || !Array.isArray(state.listItems)) return null;
  return state.listItems.find((entry) => entry.id === currentPlayerId) || null;
}

function showRenameError(message) {
  const box = document.getElementById('player-rename-error');
  box.textContent = message;
  box.hidden = false;
}

function hideRenameError() {
  const box = document.getElementById('player-rename-error');
  box.textContent = '';
  box.hidden = true;
}

function closeRenameEditor() {
  document.getElementById('player-rename-field').hidden = true;
  document.getElementById('player-rename-input').value = '';
  document.getElementById('player-rename-confirm').hidden = true;
  document.getElementById('player-rename-confirm').disabled = true;
  document.getElementById('player-rename').hidden = false;
  document.getElementById('player-title').hidden = false;
  hideRenameError();
}

function openRenameEditor() {
  const video = currentVideo();
  if (!video) return;
  hideRenameError();
  const input = document.getElementById('player-rename-input');
  input.value = video.filename;
  document.getElementById('player-rename-confirm').disabled = true;
  document.getElementById('player-title').hidden = true;
  document.getElementById('player-rename').hidden = true;
  document.getElementById('player-rename-confirm').hidden = false;
  document.getElementById('player-rename-field').hidden = false;
  input.focus();
  input.select();
}

function applyRenamedVideoName(name) {
  /* Обновить state + имя в просмотре и карточке списка (textContent —
   * XSS-дисциплина ОГР-11). Сервер уже хранит новое имя — перезагрузка
   * не нужна; polling/возврат к списку подтянут остальное (бейдж
   * расширения, поиск/сортировка — по имени с сервера). */
  const video = currentVideo();
  if (video) video.filename = name;
  document.getElementById('player-title').textContent = name;
  const card = document.querySelector(
    '.v-card[data-video-id="' + currentPlayerId + '"]'
  );
  if (card) {
    const cardTitle = card.querySelector('.v-card-title');
    if (cardTitle) cardTitle.textContent = name;
    const statusLabel =
      (video && (STATUS_LABELS[video.status] || video.status)) || 'готово';
    card.setAttribute(
      'aria-label',
      `${name} (${statusLabel}) — открыть карточку`
    );
  }
}

async function submitRename() {
  const video = currentVideo();
  const input = document.getElementById('player-rename-input');
  const title = input.value.trim();
  if (!video || !title) return; // пустое не отправляем (кнопка disabled)
  if (title === video.filename) {
    closeRenameEditor(); // без изменений — просто закрыть
    return;
  }
  const confirmBtn = document.getElementById('player-rename-confirm');
  confirmBtn.disabled = true;
  let resp;
  try {
    resp = await fetch('/api/videos/' + currentPlayerId, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
  } catch (err) {
    confirmBtn.disabled = false;
    showRenameError('Не удалось переименовать видео — сеть недоступна.');
    return;
  }
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  if (!resp.ok) {
    // 422 — невалидное имя (1–255 символа, без «/» и «\»); 404 — видео
    // удалено в другом окне; остальное — общий текст (сцена 7.2).
    if (resp.status === 422) {
      showRenameError(
        'Имя не сохранено: нужно 1–255 символов, без «/» и «\\».'
      );
    } else if (resp.status === 404) {
      showRenameError('Видео не найдено — обновите список.');
    } else {
      showRenameError('Не удалось переименовать видео.');
    }
    confirmBtn.disabled = input.value.trim() === '';
    return;
  }
  const body = await resp.json();
  closeRenameEditor();
  applyRenamedVideoName(body.title || title);
}

function setupRename() {
  const input = document.getElementById('player-rename-input');
  const confirmBtn = document.getElementById('player-rename-confirm');
  document.getElementById('player-rename').addEventListener('click', openRenameEditor);
  confirmBtn.addEventListener('click', submitRename);
  input.addEventListener('input', () => {
    confirmBtn.disabled = input.value.trim() === '';
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (!confirmBtn.disabled) submitRename();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      closeRenameEditor();
      document.getElementById('player-rename').focus();
    }
  });
}

/* ===== Загрузка (мокап video-upload.html) ===== */

let selectedFile = null;
let uploading = false;

function setFileRow(name, meta, invalid) {
  const row = document.getElementById('file-row');
  row.hidden = false;
  row.classList.toggle('invalid', Boolean(invalid));
  document.getElementById('file-name').textContent = name;
  document.getElementById('file-meta').textContent = meta;
  document.getElementById('upload-progress').hidden = true;
}

function resetUploadForm() {
  selectedFile = null;
  uploading = false;
  document.getElementById('file-row').hidden = true;
  document.getElementById('file-input').value = '';
  document.getElementById('upload-submit-button').disabled = true;
  // Кусок D: категория — назад к «Без категории», поле новой скрыто.
  document.getElementById('up-category').value = '';
  document.getElementById('up-category-new-field').hidden = true;
  document.getElementById('up-category-new').value = '';
}

/* Категория при загрузке (кусок D): «+ Новая категория…» показывает
 * текстовое поле (мокап video-upload.html); создание — POST /api/categories
 * ядра (справочник один, общий с галереей) — id возвращается в FormData. */
async function resolveUploadCategoryId() {
  const select = document.getElementById('up-category');
  const value = select.value;
  if (!value) return null; // «Без категории»
  if (value !== 'new') return value;

  const nameInput = document.getElementById('up-category-new');
  const name = nameInput.value.trim();
  if (!name) {
    if (selectedFile) {
      setFileRow(selectedFile.name, 'Укажите название новой категории', true);
    }
    return undefined; // отмена отправки
  }
  const resp = await fetch('/api/categories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (resp.status === 401) {
    window.location.href = '/login';
    return undefined;
  }
  if (!resp.ok) {
    if (selectedFile) {
      setFileRow(selectedFile.name, 'Категория не создана — проверьте название', true);
    }
    return undefined;
  }
  const created = await resp.json(); // {id, name} — справочник галереи
  await loadCategories();
  select.value = String(created.id);
  document.getElementById('up-category-new-field').hidden = true;
  nameInput.value = '';
  return String(created.id);
}

function pickFile(file) {
  if (!file || uploading) return;
  selectedFile = file;
  document.getElementById('upload-submit-button').disabled = false;
  // Клиентская отсечка лимита (server дублирует — tasks 1.3): файл больше
  // 500 МБ показывается красной строкой, отправки нет (мокап).
  if (file.size > LIMIT_BYTES) {
    setFileRow(
      file.name,
      'Файл больше 500 МБ (' + fmtSize(file.size) + ') — загрузка отклонена',
      true
    );
    document.getElementById('upload-submit-button').disabled = true;
    return;
  }
  setFileRow(file.name, fmtSize(file.size) + ' · ' + fmtExt(file.name), false);
}

function setupUpload() {
  const dropzone = document.getElementById('dropzone');
  const input = document.getElementById('file-input');

  document.getElementById('open-upload-button').addEventListener('click', () => {
    resetUploadForm();
    showView('video-upload-view');
  });
  document.getElementById('upload-cancel-button').addEventListener('click', () => {
    resetUploadForm();
    showView('video-list-view');
    loadList();
  });
  document.getElementById('upload-back-link').addEventListener('click', (e) => {
    e.preventDefault();
    resetUploadForm();
    showView('video-list-view');
    loadList();
  });
  document.getElementById('player-back-link').addEventListener('click', (e) => {
    e.preventDefault();
    currentPlayerId = null;
    showView('video-list-view');
    loadList();
  });

  dropzone.addEventListener('click', () => input.click());
  dropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      input.click();
    }
  });
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    pickFile(e.dataTransfer.files && e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => pickFile(input.files && input.files[0]));

  document.getElementById('file-remove').addEventListener('click', resetUploadForm);

  // Кусок D: «+ Новая категория…» — показать/скрыть текстовое поле (мокап).
  document.getElementById('up-category').addEventListener('change', (e) => {
    document.getElementById('up-category-new-field').hidden = e.target.value !== 'new';
    if (e.target.value === 'new') document.getElementById('up-category-new').focus();
  });

  // Кусок D: фильтр категории в списке (мокап video-list.html).
  document.getElementById('video-category').addEventListener('change', (e) => {
    state.activeCategory = e.target.value;
    loadList();
  });

  // Кусок C (4.1): поиск по подстроке имени — debounce 300 мс, trim;
  // пустое поле возвращает весь список (сервер: пустой query — все).
  const searchInput = document.getElementById('video-search');
  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = searchInput.value.trim();
      loadList();
    }, 300);
  });

  // Кусок C (4.1): сортировка по имени (asc — «Имя А→Я», дефолт мокапа).
  document.getElementById('video-sort').addEventListener('change', (e) => {
    state.order = e.target.value;
    loadList();
  });

  // Кусок C (4.1): «Сбросить» — поиск и категория к дефолту, сортировка
  // к «Имя А→Я»; очистка возвращает весь список (Scenario «Поиск и
  // сортировка» спеки).
  document.getElementById('video-filter-reset').addEventListener('click', () => {
    state.query = '';
    state.activeCategory = '';
    state.order = 'asc';
    searchInput.value = '';
    document.getElementById('video-category').value = '';
    document.getElementById('video-sort').value = 'asc';
    loadList();
  });

  // Кусок D: реакции — поставить/перенести/снять (один голос, sdd §3).
  document.getElementById('like-button').addEventListener('click', () => sendReaction(1));
  document.getElementById('dislike-button').addEventListener('click', () => sendReaction(-1));

  // Кусок D: форма комментария — «Отправить» неактивна, пока поле пусто.
  const commentInput = document.getElementById('video-comment-input');
  commentInput.addEventListener('input', () => {
    document.getElementById('comment-send-button').disabled = !commentInput.value.trim();
  });
  document.getElementById('comment-form').addEventListener('submit', (e) => {
    e.preventDefault();
    submitComment();
  });

  // Отправка — XHR ради upload.onprogress (fetch не дает прогресс аплоада).
  document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedFile || uploading) return;
    if (selectedFile.size > LIMIT_BYTES) return;

    // Кусок D: категория («новая» создается до отправки файла).
    const categoryId = await resolveUploadCategoryId();
    if (categoryId === undefined) return; // категория не готова — отправки нет

    const form = new FormData();
    form.append('file', selectedFile);
    if (categoryId !== null) form.append('category_id', categoryId);

    const xhr = new XMLHttpRequest();
    uploading = true;
    document.getElementById('upload-submit-button').disabled = true;
    document.getElementById('upload-progress').hidden = false;

    xhr.upload.addEventListener('progress', (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.min(100, Math.round((e.loaded / e.total) * 100));
      document.getElementById('upload-progressbar').setAttribute('aria-valuenow', String(pct));
      document.getElementById('upload-progressbar-fill').style.width = pct + '%';
      document.getElementById('upload-progress-label').textContent = pct + '%';
    });
    xhr.addEventListener('load', () => {
      uploading = false;
      if (xhr.status === 201) {
        resetUploadForm();
        showView('video-list-view');
        loadList();
        return;
      }
      // 422 (превышение лимита/пустое тело) и прочие ошибки — красная строка.
      let message = 'Загрузка отклонена сервером';
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status === 422 && body.error === 'validation error') {
          message = 'Файл больше 500 МБ — загрузка отклонена';
        } else if (body && body.error) {
          message = 'Ошибка: ' + body.error;
        }
      } catch (err) { /* тело не JSON — оставляем общий текст */ }
      setFileRow(selectedFile.name, message, true);
      document.getElementById('upload-submit-button').disabled = false;
    });
    xhr.addEventListener('error', () => {
      uploading = false;
      setFileRow(selectedFile.name, 'Сеть недоступна — загрузка не отправлена', true);
      document.getElementById('upload-submit-button').disabled = false;
    });

    xhr.open('POST', '/api/videos');
    xhr.send(form);
  });
}

/* ===== Удаление с подтверждением (модалка мокапа video-view.html) ===== */

function setupDelete() {
  const overlay = document.getElementById('delete-overlay');

  document.getElementById('delete-open-button').addEventListener('click', () => {
    if (!currentPlayerId) return;
    document.getElementById('delete-video-name').textContent =
      '«' + document.getElementById('player-title').textContent + '»';
    overlay.hidden = false;
  });
  const close = () => { overlay.hidden = true; };
  document.getElementById('delete-cancel-button').addEventListener('click', close);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.hidden) close();
  });

  document.getElementById('delete-confirm-button').addEventListener('click', async () => {
    if (!currentPlayerId) return;
    const resp = await fetch('/api/videos/' + currentPlayerId, { method: 'DELETE' });
    if (resp.status === 401) {
      window.location.href = '/login';
      return;
    }
    overlay.hidden = true;
    currentPlayerId = null;
    showView('video-list-view');
    loadList();
  });
}

async function init() {
  setupUpload();
  setupDelete();
  setupRename();
  showView('video-list-view');
  // Кусок D: кто я (кнопка «удалить» у своих) + справочник категорий —
  // параллельно списку; сбой /me не блокирует страницу (комментарии
  // просто рендерятся без кнопок удаления).
  try {
    const [meResp] = await Promise.allSettled([fetch('/api/auth/me')]);
    if (meResp.status === 'fulfilled' && meResp.value.ok) {
      state.me = await meResp.value.json();
    }
  } catch (err) { /* /me недоступен — страница работает без «удалить» */ }
  loadCategories();
  loadList();
}

init();

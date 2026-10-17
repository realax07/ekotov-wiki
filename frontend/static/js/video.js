/* Страница «Видео» — tasks.md 1.5 video-hosting (волна 1, кусок A).
 *
 * Вид — по утвержденным мокапам 0.2 (design/video-hosting/video-list.html,
 * video-upload.html, video-view.html); селекторы — дословно из макетов.
 * Кусок D (комментарии/лайки/категории) и поиск/сортировка (кусок C)
 * НЕ входят — свои задачи (2.4, 4.1).
 *
 * Данные — API video-сервиса (за сессией, NFR-36):
 *   GET    /api/videos               — список;
 *   POST   /api/videos               — загрузка multipart (≤ 500 МБ);
 *   DELETE /api/videos/{id}          — удаление;
 *   GET    /api/videos/{id}/preview  — кадр (409 = плейсхолдер по макету).
 * Файл для плеера — file_url из списка (nginx /videos/<id>/…, design §5).
 * Статусы: uploaded «загружено» / converting «конвертируется» /
 * ready «готово» / error «ошибка»; плеер — ТОЛЬКО для «готово»
 * (Scenario «Не готовое видео не проигрывается»).
 */

const LIMIT_BYTES = 500 * 1024 * 1024; // ОВ-1: до 500 МБ включительно

const STATUS_LABELS = {
  uploaded: 'загружено',
  converting: 'конвертируется',
  ready: 'готово',
  error: 'ошибка',
};

const views = ['video-list-view', 'video-upload-view', 'video-player-view'];

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
  const size = document.createElement('span');
  size.textContent = fmtSize(item.size_bytes);
  const date = document.createElement('span');
  date.textContent = '· ' + fmtDate(item.created_at);
  meta.append(size, date);
  body.append(title, meta);

  card.append(thumb, body);
  card.addEventListener('click', (e) => {
    e.preventDefault();
    openPlayer(item);
  });
  return card;
}

async function loadList() {
  const grid = document.getElementById('video-grid');
  const empty = document.getElementById('video-empty');
  grid.querySelectorAll('.v-card').forEach((el) => el.remove());

  const resp = await fetch('/api/videos');
  if (resp.status === 401) {
    window.location.href = '/login';
    return;
  }
  const data = await resp.json();
  const videos = data.videos || [];
  document.getElementById('video-count').textContent = 'Видео: ' + videos.length;
  for (const item of videos) {
    grid.append(buildCard(item));
  }
  empty.hidden = videos.length > 0;
}

/* ===== Просмотр (мокап video-view.html) ===== */

let currentPlayerId = null;

function openPlayer(item) {
  currentPlayerId = item.id;
  document.getElementById('player-title').textContent = item.filename;

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
    card.append(pending);
  }

  const statusCell = document.getElementById('player-status');
  statusCell.innerHTML = '';
  statusCell.append(statusBadge(item.status));
  document.getElementById('player-size').textContent = fmtSize(item.size_bytes);
  document.getElementById('player-date').textContent = fmtDate(item.created_at);

  showView('video-player-view');
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

  // Отправка — XHR ради upload.onprogress (fetch не дает прогресс аплоада).
  document.getElementById('upload-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!selectedFile || uploading) return;
    if (selectedFile.size > LIMIT_BYTES) return;

    const form = new FormData();
    form.append('file', selectedFile);

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

function init() {
  setupUpload();
  setupDelete();
  showView('video-list-view');
  loadList();
}

init();

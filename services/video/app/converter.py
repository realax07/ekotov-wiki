"""Фоновая конвертация видео (tasks 3.1, волна 3, кусок B; design §3; sdd §2).

Единственный владелец очереди и subprocess ffmpeg — этот модуль (шов:
videos.py вызывает converter.enqueue/cancel, статусы пишет ТОЛЬКО
поток-воркер, API — читатель; файлы — только через storage.*):

- очередь queue.Queue + ровно 1 поток-воркер (серийность: одна конвертация
  одновременно — design §3, NFR-35); start_worker() — на старте main.py;
- subprocess ffmpeg: nice 10 (preexec_fn), wall-clock таймаут 30 мин
  (истечение = kill = неудача попытки), `-c:v libx264 -preset veryfast
  -movflags +faststart`; превью-кадр `-frames:v 1` тем же проходом —
  В ТОМ ЧИСЛЕ для исходника, уже являющегося mp4 (быстрый проход без
  перекодирования: конвертация скипается, снимается только кадр);
- статусы в БД: uploaded → converting → ready / error; ровно ОДИН
  авторетрай (non-zero exit / timeout / нет выходного файла / не снялся
  кадр); после второй неудачи — error, оригинал СОХРАНЕН (ТЗ);
- успех: video.mp4 + preview.jpg в томе, оригинал удален (для уже-mp4
  исходник и есть готовое mp4 — остается под своим именем, playable_path
  его отдает), size_bytes обновлен;
- отмена при DELETE: cancel(id) ставит in-memory флаг; воркер проверяет
  его перед записью результата — артефакты отбрасываются, статус не
  пишется (гонка «флаг сразу после проверки» — принята: DELETE сам
  удаляет строку и каталог, повторная чистка артефактов идемпотентна);
- крэш-восстановление (устранение F1): recover_pending() на старте —
  записи в статусах uploaded И converting переводятся в uploaded и
  re-enqueue (частичный mp4/кадр прерванного прохода удаляются перед
  повтором). Инвариант design §3: после старта воркера в БД нет
  uploaded/converting, которых нет в очереди.

env: EKOTOV_WIKI_FFMPEG — путь к бинарю (дефолт «ffmpeg»; в образе —
/usr/local/bin/ffmpeg из johnvansickle-тарболла, tasks 1.2);
EKOTOV_WIKI_CONVERTER=off — не запускать воркер на старте main
(сервисные тесты кусков A/D: статус должен быть детерминирован).
"""

import logging
import os
import queue
import subprocess
import threading

from app import storage
from app.db import get_connection

log = logging.getLogger("video.converter")

# Wall-clock таймаут ОДНОЙ попытки ffmpeg (design §3: 500 МБ worst-case).
# Читается при каждом запуске — тесты сужают через monkeypatch.
CONVERT_TIMEOUT_SECONDS = 30 * 60

# Ровно один авторетрай: суммарно не больше 2 попыток (sdd §4: 0..2).
MAX_ATTEMPTS = 2

# Кодирование (design §3): faststart — прогрессивная отдача <video>.
VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-movflags", "+faststart"]
# Превью-кадр — первый кадр (для уже-mp4 — тот же дешевый проход).
PREVIEW_ARGS = ["-frames:v", "1"]

_queue: "queue.Queue" = queue.Queue()
_cancel_lock = threading.Lock()
_cancelled: set[str] = set()
_worker: threading.Thread | None = None


def ffmpeg_bin() -> str:
    """Путь к ffmpeg: env EKOTOV_WIKI_FFMPEG или «ffmpeg» из PATH.

    Читается на каждый запуск (не на импорт): путь — конфигурация
    окружения, тесты подменяют на скрипт-заглушку (tasks 3.2)."""
    return os.environ.get("EKOTOV_WIKI_FFMPEG", "ffmpeg")


def enqueue(video_id: str) -> None:
    """Постановка в очередь (шов из videos.py; заглушка куска A заменена)."""
    _queue.put(video_id)


def cancel(video_id: str) -> None:
    """Флаг отмены (in-memory): DELETE во время конвертации (design §3)."""
    with _cancel_lock:
        _cancelled.add(video_id)


def _is_cancelled(video_id: str) -> bool:
    with _cancel_lock:
        return video_id in _cancelled


def _unmark_cancelled(video_id: str) -> None:
    with _cancel_lock:
        _cancelled.discard(video_id)


def queued() -> list[str]:
    """Снимок очереди (диагностика/тесты; порядок не гарантирован)."""
    return list(_queue.queue)


def _lower_priority() -> None:  # preexec_fn: в fork-ребенке до exec
    os.nice(10)  # design §3: пониженный приоритет CPU против API


def _run_ffmpeg(args: list[str]) -> bool:
    """Одна команда ffmpeg с wall-clock таймаутом; True = exit 0.

    Истечение таймаута — subprocess.run сам убивает процесс и ждет:
    зависший ffmpeg не может блокировать очередь дольше таймаута
    (design §3)."""
    cmd = [ffmpeg_bin(), "-nostdin", "-y"] + args
    try:
        proc = subprocess.run(  # noqa: S603 — аргументы без пользовательских имен
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=CONVERT_TIMEOUT_SECONDS,
            preexec_fn=_lower_priority,
        )
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg timeout (%ss): %s", CONVERT_TIMEOUT_SECONDS, args[-1])
        return False
    except OSError as exc:
        log.error("ffmpeg failed to start: %s", exc)
        return False
    return proc.returncode == 0


def _set_fields(video_id: str, **fields) -> None:
    """Обновление строки записи. Писатель статуса — ТОЛЬКО воркер
    (design §3); API-строка к этому моменту существует: DELETE удаляет
    строку до/параллельно — UPDATE в 0 строк не ошибка."""
    conn = get_connection()
    try:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE video_videos SET {cols} WHERE id = ?",
            (*fields.values(), video_id),
        )
        conn.commit()
    finally:
        conn.close()


def _get_row(video_id: str):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, status, convert_attempts FROM video_videos WHERE id = ?",
            (video_id,),
        ).fetchone()
    finally:
        conn.close()


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _discard_artifacts(video_id: str) -> None:
    """Отбросить артефакты попытки (частичный mp4/кадр) — при отмене и
    перед ретраем; original.<ext> НЕ трогается (он — данные воркера)."""
    _remove(storage.mp4_path(video_id))
    _remove(storage.preview_path(video_id))


def _attempt(orig: str, mp4: str, preview: str, is_mp4: bool) -> bool:
    """Одна попытка: (перекодирование,) кадр. Неудача попытки — non-zero
    exit / timeout / нет выходного файла / не снялся кадр (design §3)."""
    if not is_mp4:
        if not _run_ffmpeg(["-i", orig] + VIDEO_ARGS + [mp4]):
            return False
        if not os.path.isfile(mp4):
            return False
        src = mp4
    else:
        src = orig  # уже mp4: перекодирование скипается, кадр — из исходника
    if not _run_ffmpeg(["-i", src] + PREVIEW_ARGS + [preview]):
        return False
    return os.path.isfile(preview)


def process_one(video_id: str) -> None:
    """Полный цикл одной записи: converting → попытки (≤2) → ready/error.

    Синхронный — воркер-поток вызывает его из очереди; тесты (3.2)
    вызывают напрямую для детерминизма. Не бросает исключений наружу:
    воркер-поток не должен умирать на одной записи.
    """
    try:
        _process(video_id)
    except Exception:  # noqa: BLE001 — выживание потока важнее причины
        log.exception("converter: unexpected failure on %s", video_id)
    finally:
        _unmark_cancelled(video_id)


def _process(video_id: str) -> None:
    if _is_cancelled(video_id):
        # Удалено до старта воркера: артефактов быть не должно, но чистим
        # идемпотентно (гонка DELETE↔старт), статус не пишем.
        _discard_artifacts(video_id)
        return

    row = _get_row(video_id)
    if row is None:
        return  # удалено до старта (DELETE) — писать статус некуда

    orig = storage.find_original(video_id)
    if orig is None:
        # Крэш без исходника (том потерян) — обслуживать нечего: error.
        log.error("converter: original missing for %s", video_id)
        _set_fields(video_id, status="error")
        return

    # Статус converting пишет ТОЛЬКО воркер (design §3).
    _set_fields(video_id, status="converting")

    ext = os.path.basename(orig).split(".", 1)[1]
    is_mp4 = ext == "mp4"
    mp4 = storage.mp4_path(video_id)
    preview = storage.preview_path(video_id)

    attempts = int(row["convert_attempts"] or 0)
    while True:
        if _is_cancelled(video_id):
            _discard_artifacts(video_id)
            return
        attempts += 1
        _set_fields(video_id, convert_attempts=attempts)
        if _attempt(orig, mp4, preview, is_mp4):
            break
        # Неудача попытки: частичный mp4/кадр удаляются перед повтором
        # (design §3 «частичный mp4 удалить перед повтором»; в error —
        # тем более: сломанный mp4 не должен выглядеть готовым).
        _discard_artifacts(video_id)
        if attempts >= MAX_ATTEMPTS:
            _set_fields(video_id, status="error")
            log.warning(
                "converter: %s failed after %d attempts — original kept", video_id, attempts
            )
            return

    if _is_cancelled(video_id):
        # Удаление во время конвертации: артефакты отбрасываются,
        # ничего не пишется (строку уже удалил DELETE).
        _discard_artifacts(video_id)
        return

    # Успех: mp4+preview в томе, оригинал удален, размер обновлен.
    # Для уже-mp4 исходника перекодирования не было — оригинал и есть
    # готовое видео (storage.playable_path отдает его без video.mp4).
    final_size = os.path.getsize(orig) if is_mp4 else os.path.getsize(mp4)
    _set_fields(video_id, status="ready", size_bytes=final_size)
    if not is_mp4:
        _remove(orig)
    log.info("converter: %s ready (%d bytes, attempts=%d)", video_id, final_size, attempts)


def _worker_loop() -> None:
    while True:
        video_id = _queue.get()
        try:
            if video_id is None:  # sentinel stop_worker()
                return
            process_one(video_id)
        finally:
            _queue.task_done()


def recover_pending() -> int:
    """Крэш-восстановление (design §3, устранение F1): записи uploaded И
    converting → статус uploaded + re-enqueue; частичные mp4/кадр
    прерванного прохода удаляются. Возвращает число re-enqueue."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, status FROM video_videos WHERE status IN ('uploaded', 'converting')"
        ).fetchall()
        for row in rows:
            if row["status"] == "converting":
                _discard_artifacts(row["id"])
            conn.execute(
                "UPDATE video_videos SET status = 'uploaded' WHERE id = ?", (row["id"],)
            )
        conn.commit()
    finally:
        conn.close()
    for row in rows:
        enqueue(row["id"])
    if rows:
        log.info("converter: recovered %d pending record(s)", len(rows))
    return len(rows)


def stop_worker() -> None:
    """Остановка потока-воркера (тестовая гигиена 3.2: воркер одного
    тест-модуля не должен обслуживать очередь другого). В проде не
    вызывается — воркер живет весь процесс."""
    global _worker
    if _worker is None:
        return
    thread, _worker = _worker, None
    _queue.put(None)  # sentinel: поток завершается после текущей задачи
    thread.join(timeout=30)


def start_worker() -> threading.Thread | None:
    """Крэш-восстановление + запуск ровно одного потока-воркера.

    Идемпотентен (повторный вызов поток не плодит). Вызывается на старте
    main.py; при env EKOTOV_WIKI_CONVERTER=off не делает ничего
    (сервисные тесты: статус-писателя нет — записи остаются uploaded)."""
    global _worker
    if os.environ.get("EKOTOV_WIKI_CONVERTER", "on") == "off":
        return None
    if _worker is not None and _worker.is_alive():
        return _worker
    recover_pending()
    _worker = threading.Thread(target=_worker_loop, name="video-converter", daemon=True)
    _worker.start()
    log.info("converter: worker started")
    return _worker

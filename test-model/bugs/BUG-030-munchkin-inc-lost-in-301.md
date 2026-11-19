# BUG-030 — games-proxy-munchkin.inc утерян при коммите #301

**Симптом:** e2e-стенд (wiki-test) не поднимается: netdata-1 nginx emerg —
`open() "/etc/nginx/conf.d/games-proxy-munchkin.inc" failed` в ekotov-wiki.conf:320
(conf на main ссылается на include, файла в git нет).

**Корень:** коммит волны «munchkin standalone» включил правку ekotov-wiki.conf,
но новый untracked inc-файл не попал в `git add services/frontend/nginx/`
(потерян при checkout-переключениях ПМ между ветками).

**Фикс:** восстановление содержимого inc (прокси стендалона munchkin:8080
со срезом префикса, анти-stale-DNS переменная).

**Диагностика:** CI PR #301 e2e «стенд не поднялся за 120s» + лог netdata-1;
локальный повтор `openspec validate`/`flow_check` чисто — ловится только
e2e-стендом (nginx -t в контейнере).

**Статус:** CLOSED этим PR (вернуть файл в git).

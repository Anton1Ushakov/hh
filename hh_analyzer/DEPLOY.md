# Деплой HH Analytics

## Что нужно в любом случае

### 1. OAuth-приложение на dev.hh.ru

- `HH_CLIENT_ID`, `HH_CLIENT_SECRET`
- Redirect URI **точно** совпадает с продакшен-URL:  
  `https://ВАШ-ДОМЕН/auth/callback`
- Роль **employer** (для поиска резюме)
- `HH_REFRESH_TOKEN` (или авторизация через `/auth/login` после деплоя)

### 2. Переменные окружения

| Переменная | Обязательно | Пример |
|------------|-------------|--------|
| `HH_CLIENT_ID` | да | из dev.hh.ru |
| `HH_CLIENT_SECRET` | да | из dev.hh.ru |
| `HH_REDIRECT_URI` | да | `https://hh.example.com/auth/callback` |
| `HH_REFRESH_TOKEN` | да* | refresh token |
| `HH_USER_AGENT` | да | `HH-Analytics (you@mail.ru)` |
| `HH_ACCESS_TOKEN` | нет | обновится сам |
| `DATABASE_URL` | нет | `sqlite:////data/hh_analyzer.db` (с volume) |
| `PORT` | нет | `8000` (Coolify/Docker задают сами) |

\* Можно получить после деплоя через `/auth/login`, если redirect URI настроен.

### 3. Рантайм

Нужен **долгоживущий Python-сервер** (FastAPI + uvicorn), не serverless.

- ✅ Coolify, Render, Railway, Fly.io, VPS + Docker
- ❌ **Vercel** — не подходит (см. ниже)

---

## Coolify (рекомендуется, если есть VPS)

Coolify — self-hosted PaaS: Git → Docker → домен + HTTPS. У вас уже есть `Dockerfile` и `docker-compose.yml`.

### Что нужно заранее

1. VPS (Hetzner ~€4/мес, Timeweb, и т.д.)
2. [Coolify](https://coolify.io) установлен на сервер (one-click или скрипт с сайта)
3. Репозиторий на GitHub с кодом в папке `hh_analyzer`

### Шаги

1. Coolify → **New Resource** → **Application**
2. Источник: **GitHub** → репозиторий `hh`
3. **Base Directory**: `hh_analyzer`
4. **Build Pack**: Dockerfile (или Docker Compose)
5. **Environment Variables** — все `HH_*` из таблицы выше  
   `HH_REDIRECT_URI` = `https://ваш-домен.ru/auth/callback`
6. **Persistent Storage** (важно для истории и токенов):
   - Mount path: `/data`
   - `DATABASE_URL=sqlite:////data/hh_analyzer.db`
7. Домен в Coolify → Let's Encrypt включится автоматически
8. **dev.hh.ru** → добавить тот же redirect URI
9. Deploy

### Проверка

- `https://ваш-домен/health` → `{"status":"ok",...}`
- `/` — расчёт
- `/auth/login` — если нет refresh token

### Локально через Compose

```bash
cd hh_analyzer
cp .env.example .env   # заполнить секреты
docker compose up --build
```

---

## Почему не Vercel

Vercel заточен под **Next.js / статику / короткие serverless-функции**.

HH Analytics — это:

- постоянный **uvicorn**-процесс;
- **SQLite** с историей запросов и OAuth-токенами;
- OAuth callback и фоновая загрузка справочников при старте.

На Vercel пришлось бы переписывать под serverless, менять БД на внешнюю (Postgres/Redis) и терять простоту. **Не стоит.**

---

## Render (облако без своего VPS)

Если VPS не нужен — см. `render.yaml` в этой папке.

1. render.com → Blueprint → repo `hh`
2. Те же env-переменные
3. Минус free tier: сервис засыпает, SQLite может сброситься при redeploy

---

## Обновление refresh token

HH выдаёт новый refresh при каждом refresh. Приложение сохраняет пару в SQLite. Если `invalid_grant` — снова `/auth/login` или обновите `HH_REFRESH_TOKEN` в env Coolify.

# Frontend Sketch

Черновой интерфейс для MVP на `React + Vite`.

## Что внутри

- левое меню с переходами: создание заявки, история, вызов AI-чата
- форма создания заявки
- история с переходом в предзаполненную форму
- правая сворачиваемая панель будущей нейросети

## Запуск

```bash
cd frontend
npm install
npm run dev
```

## Следующий шаг

Подключить реальные вызовы к backend:

- `POST /api/search/query`
- `POST /api/drafts/from-search`
- `POST /api/drafts/evaluate`

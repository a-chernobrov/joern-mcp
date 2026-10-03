# Joern MCP Server

MCP-сервер для взаимодействия с [Joern](https://joern.io/) — платформой для анализа исходного кода и построения графов свойств кода (CPG — Code Property Graph).

Сервер общается с Joern через синхронный HTTP-эндпоинт `/query-sync`, поэтому не требует опроса состояния и подходит для выполнения любых CPGQL-запросов.

## Возможности

Сервер предоставляет три MCP-инструмента:

| Инструмент         | Назначение                                                             |
| ------------------ | ---------------------------------------------------------------------- |
| `joern_query`      | Выполнить произвольный Joern/CPGQL-запрос к загруженному CPG           |
| `joern_load`       | Загрузить исходный код и построить CPG (PHP, Java, JS, Python, C/C++…) |
| `joern_workspace`  | Показать загруженные проекты и активный CPG в рабочем пространстве      |

## Требования

- Python 3.10+
- [Joern](https://docs.joern.io/installation/) — запущенный сервер (`joern --server`) на `http://localhost:8080`
- Python-пакет `mcp`

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

1. Запустите сервер Joern:

   ```bash
   joern --server
   ```

2. Подключите MCP-сервер к вашему клиенту (например, Trae). Пример конфигурации:

   ```json
   {
     "mcpServers": {
       "joern": {
         "command": "python3",
         "args": ["/абсолютный/путь/к/server.py"]
       }
     }
   }
   ```

## Интерактивный REPL

Для ручного выполнения запросов без MCP-клиента есть простой REPL:

```bash
python3 repl.py
```

После запуска вводите CPGQL-запросы в приглашении `joern>`.

## Примеры запросов

```scala
cpg.method.name.l
cpg.call.name("exec").caller.name.l
cpg.identifier.name("_GET|_POST").l
cpg.method.name("login").ast.isCall.name.l
sink.reachableByFlows(source).p
```

## Структура проекта

```
.
├── server.py         # MCP-сервер (инструменты joern_query / joern_load / joern_workspace)
├── repl.py           # Интерактивный REPL для ручных запросов
├── requirements.txt  # Python-зависимости
└── LICENSE           # GNU GPL v3.0
```

## Переменные среды

Параметры подключения заданы в `server.py` и могут быть изменены:

- `JOERN_BASE` — адрес сервера Joern (по умолчанию `http://localhost:8080`)
- `TIMEOUT` — таймаут запроса в секундах (по умолчанию `120`)
- `MAX_RESULT` — максимальная длина вывода в символах (по умолчанию `8000`)

## Лицензия

Проект распространяется под лицензией [GNU General Public License v3.0](LICENSE).

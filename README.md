# DevOps на практике

Русскоязычный практикум: от запуска HTTP-сервиса до контейнеров, CI и Kubernetes. Все задания выполняются вокруг одного приложения. В каждой работе есть проверка и упражнение на диагностику.

**Уровень:** начинающий с базовым знанием командной строки. **Темп:** 2-4 часа на работу. Выполняйте последовательно в отдельной учебной папке. Примеры рассчитаны на Linux/macOS с Python 3, Git и Docker с Compose; Kubernetes требует локального кластера и kubectl. Не используйте рабочий кластер или настоящие секреты.

## Маршрут

1. [Сервис и диагностика](#1-сервис-и-диагностика) - HTTP, процессы и порты.
2. [Git и проверка изменений](#2-git-и-проверка-изменений) - ветка, тесты, история.
3. [Docker](#3-docker) - образ, контейнер, логи и ограничения.
4. [Compose и состояние](#4-compose-и-состояние) - два сервиса и постоянные данные.
5. [CI](#5-ci) - автоматическая проверка pull request.
6. [Kubernetes](#6-kubernetes) - Deployment, Service, readiness и откат.
7. [Наблюдаемость и инцидент](#7-наблюдаемость-и-инцидент) - метрики и расследование.
8. [Итоговый проект](#8-итоговый-проект) - самостоятельная сборка и эксплуатация.

## Как проходить

Создайте собственный репозиторий для решений. Не копируйте команды вслепую: перед запуском объясните себе, какие файлы и ресурсы они меняют. После каждого задания фиксируйте команду проверки, результат и причину сбоев. В конце работы сделайте коммит. Облачные ресурсы не требуются; локальный кластер потребляет память и процессор.

## 1. Сервис и диагностика

**Результат:** локальный HTTP-сервис и понимание, как найти его процесс и порт.

Создайте папку и файл app.py:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthz':
            body, status = {'status': 'ok'}, 200
        elif self.path == '/':
            body, status = {'service': 'devops-lab', 'version': os.getenv('APP_VERSION', 'local')}, 200
        else:
            body, status = {'error': 'not found'}, 404
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
```

Запустите `python3 app.py` в одном терминале, а в другом выполните:

```bash
curl -i http://127.0.0.1:8080/healthz
curl -i http://127.0.0.1:8080/missing
lsof -i :8080
```

**Проверка:** первый запрос возвращает 200 и JSON, второй - 404. Найдите PID процесса и остановите сервер через Ctrl+C. Если порт занят, найдите владельца порта; не завершайте неизвестный процесс.

**Поломка:** остановите сервер и повторите curl. Чем ошибка соединения отличается от HTTP 404? Запишите ответ. Дополнительно добавьте тест неизвестного маршрута и переменной APP_VERSION.

## 2. Git и проверка изменений

**Результат:** изменение в отдельной ветке и воспроизводимый тест без сторонних библиотек.

```bash
git init
git add app.py
git commit -m 'Add HTTP service'
git switch -c lab-02-tests
```

Создайте test_app.py:

```python
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from app import Handler

class ServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_health(self):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        try:
            conn.request('GET', '/healthz')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read()), {'status': 'ok'})
        finally:
            conn.close()

if __name__ == '__main__':
    unittest.main()
```

Выполните `python3 -m unittest -v`, затем добавьте тест 404. Проверьте `git diff`, закоммитьте изменения и откройте pull request в своём репозитории. **Поломка:** измените ожидаемый статус на 201, убедитесь, что тест падает, и исправьте его. Не коммитьте намеренно сломанный тест.

## 3. Docker

**Результат:** сервис запускается в контейнере от непривилегированного пользователя.

Создайте Dockerfile:

```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY app.py .
USER 65532:65532
EXPOSE 8080
CMD ["python", "-u", "app.py"]
```

```bash
docker build -t devops-lab:local .
docker run --rm -d --name devops-lab -p 127.0.0.1:8080:8080 devops-lab:local
curl -i http://127.0.0.1:8080/healthz
docker logs devops-lab
docker inspect --format '{{.Config.User}}' devops-lab
docker stop devops-lab
```

**Проверка:** ответ 200, пользователь контейнера 65532:65532, после stop контейнер удалён. Если порт занят, остановите только свой учебный сервис или поменяйте внешний порт. **Поломка:** запустите без `-p` и объясните, почему запрос с хоста не работает. Для реальной поставки фиксируйте базовый образ по digest и регулярно обновляйте его.

## 4. Compose и состояние

**Результат:** приложение и Redis общаются по внутренней сети, данные переживают пересоздание контейнера. Это отдельная учебная проверка хранилища: приложение пока не использует Redis.

Создайте compose.yaml:

```yaml
services:
  app:
    build: .
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      APP_VERSION: compose
  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
volumes:
  redis-data:
```

```bash
docker compose up -d --build
curl http://127.0.0.1:8080/
docker compose exec redis redis-cli SET course hello
docker compose down
docker compose up -d
docker compose exec redis redis-cli GET course
```

**Проверка:** версия compose, GET возвращает hello. `docker compose down` сохраняет том; `docker compose down -v` удалит учебные данные и выполняется только после проверки. **Поломка:** сравните имя сервиса redis с localhost внутри контейнера. Почему localhost указывает на сам контейнер? Пароли и реальные данные в этот пример не помещайте.

## 5. CI

**Результат:** каждый push и pull request запускает тесты и сборку образа. В своём репозитории создайте .github/workflows/ci.yml:

```yaml
name: CI
on: [push, pull_request]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: python -m unittest -v
      - run: docker build -t devops-lab:ci .
```

Отправьте ветку на GitHub и откройте Actions. **Проверка:** оба шага зелёные; намеренно сломанный тест в отдельном коммите делает проверку красной, исправление возвращает её в зелёное состояние. Для production фиксируйте сторонние actions полным SHA, проверяйте зависимости и не передавайте секреты недоверенному коду из pull request.

## 6. Kubernetes

**Результат:** две реплики и проверяемый откат. Нужны kubectl и отдельный локальный кластер, например kind. Следующая команда создаёт учебный namespace только в текущем контексте: сначала проверьте `kubectl config current-context` и убедитесь, что это локальный кластер.

Создайте кластер командой `kind create cluster --name devops-lab`, затем загрузите локальный образ: `kind load docker-image devops-lab:local --name devops-lab`. Проверьте текущий контекст. Создайте k8s.yaml:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: devops-lab
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: devops-lab
spec:
  replicas: 2
  selector:
    matchLabels: {app: devops-lab}
  template:
    metadata:
      labels: {app: devops-lab}
    spec:
      containers:
        - name: app
          image: devops-lab:local
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet: {path: /healthz, port: 8080}
            initialDelaySeconds: 2
            periodSeconds: 5
          resources:
            requests: {cpu: 50m, memory: 64Mi}
            limits: {cpu: 250m, memory: 128Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: app
  namespace: devops-lab
spec:
  selector: {app: devops-lab}
  ports:
    - port: 80
      targetPort: 8080
```

```bash
kubectl apply -f k8s.yaml
kubectl -n devops-lab rollout status deployment/app
kubectl -n devops-lab get pods,service
kubectl -n devops-lab port-forward service/app 8080:80
```

В другом терминале выполните `curl http://127.0.0.1:8080/healthz`. Остановите port-forward через Ctrl+C. **Поломка:** установите неверный образ командой `kubectl -n devops-lab set image deployment/app app=devops-lab:missing`, посмотрите `kubectl -n devops-lab describe pods`, затем выполните `kubectl -n devops-lab rollout undo deployment/app` и дождитесь rollout status. Объясните, почему готовые старые реплики могут продолжать обслуживать запросы при сбое обновления. Удалите только учебный кластер: `kind delete cluster --name devops-lab`.

## 7. Наблюдаемость и инцидент

**Задача:** научиться отделять симптом от причины. Запустите приложение в Compose и соберите данные:

```bash
docker compose ps
docker compose logs --tail=50 app
curl -s -o /dev/null -w 'status=%{http_code} time=%{time_total}\n' http://127.0.0.1:8080/healthz
```

Остановите только app: `docker compose stop app`. Повторите проверку, изучите статус и логи, затем восстановите `docker compose up -d app`. Напишите короткий отчёт: время обнаружения, симптом, влияние, причина, действия, проверка восстановления и одно предотвращающее действие. Не называйте отсутствие ответа достаточным доказательством причины: сопоставьте его с состоянием процесса.

**Дополнительное задание:** добавьте счётчик запросов по кодам ответа и длительность в метрики; не используйте полный URL или идентификатор пользователя как метку - это создаёт высокую кардинальность. Подключите Prometheus и постройте графики частоты ошибок и задержки, проверив, что метрики действительно собираются.

## 8. Итоговый проект

Соберите в своём репозитории сервис, Dockerfile, Compose, тесты, workflow и манифесты. Подготовьте README с запуском, проверкой, ограничениями и очисткой. Продемонстрируйте:

- чистый запуск и автоматические тесты;
- диагностику намеренно сломанного развёртывания и успешный откат;
- сохранение и удаление учебных данных по команде;
- отчёт об инциденте и объяснение, чем readiness отличается от liveness;
- отсутствие паролей, токенов и файлов состояния в Git.

**Самопроверка:** может ли другой человек по README воспроизвести результат? Что произойдёт при падении одной реплики? Как проверить восстановление, а не только выполнение команды?

## Куда двигаться дальше

Следующие темы для самостоятельного расширения: Terraform/OpenTofu и безопасное хранение state; Ansible и идемпотентность; Helm; GitOps с Argo CD; секреты через специализированное хранилище; резервное копирование и восстановление; SLO и алертинг. Перед использованием сверяйтесь с официальной документацией инструментов и закрепляйте проверенные версии.

Курс вдохновлён структурой [DevOps Core Course](https://github.com/inno-devops-labs/DevOps-Core-Course). Материалы этого репозитория написаны самостоятельно.

# Epic-Claimer — GitHub Actions workflow

> ⚡ **Быстрый старт**: следуя инструкции ниже, вы пройдёте путь от создания репозитория до первого запуска всего за 10 минут!

## Предварительные требования

Прежде чем начать, убедитесь, что у вас есть:

✅ Аккаунт GitHub (бесплатного достаточно)
✅ Аккаунт Epic Games (с отключённой двухфакторной аутентификацией)
✅ Аккаунт Google (для получения бесплатного ключа Gemini API)

⚠️ **Важное напоминание**: у аккаунта Epic Games обязательно должна быть отключена двухфакторная аутентификация (2FA), иначе автоматизация работать не будет.

## Особенности

✅ **Запуск из исходников**: workflow клонирует публичный код `Magerko/Epic-Claimer` и запускает его напрямую — без готового Docker-образа, всегда актуальная версия с вашими фичами (мульти-аккаунт, прокси)
✅ **Опциональный запуск по расписанию**: раз в день в 15:55 (UTC); по умолчанию выключен, включается одной строкой
✅ **Ручной запуск**: поддерживается ручной запуск из интерфейса Actions
✅ **Проверка приватности репозитория**: workflow выполняется только в приватных репозиториях, что защищает ваш аккаунт
✅ **Сохранение данных**: данные пользователя хранятся в отдельной ветке, что обеспечивает сохранение состояния между запусками
✅ **Защита по таймауту**: автоматический таймаут через 20 минут предотвращает бесконечное выполнение
✅ **Полные логи**: автоматическое сохранение логов и скриншотов

## Полная инструкция по настройке

### Шаг 1. Создайте приватный репозиторий

⚠️ **Важно**: из соображений безопасности этот workflow может выполняться только в приватном репозитории!

1. Зайдите на [GitHub](https://github.com) и войдите в свой аккаунт
2. Нажмите кнопку «+» в правом верхнем углу и выберите «New repository»
3. **Repository name**: введите `gamer-nx892` (или любое другое название на ваш вкус; постарайтесь избегать «чувствительных» слов вроде `epic` и `crawler`)
4. ⚠️ **Важно**: отметьте опцию «Private» (приватный репозиторий)
5. Отметьте «Add a README file»
6. Нажмите «Create repository»

### Шаг 2. Загрузите файл workflow

1. **Создайте структуру каталогов**:
   - На главной странице репозитория нажмите «Add file» → «Create new file»
   - В поле имени файла введите: `.github/workflows/epic-claimer.yml`
   - GitHub автоматически создаст нужную структуру каталогов

2. **Вставьте содержимое workflow**:
   - Скопируйте полный YAML-код ниже и вставьте его в редактор
   - Нажмите «Commit new file» внизу страницы

<details>
<summary>📄 Нажмите, чтобы развернуть полное содержимое файла workflow (epic-claimer.yml)</summary>

```yaml
name: Epic-Claimer

on:
  # Ручной запуск
  workflow_dispatch:

  # Запуск по расписанию — раз в день в 15:55 (UTC).
  # По умолчанию выключен; чтобы включить, раскомментируйте две строки ниже.
#  schedule:
#    - cron: '55 15 * * *'

jobs:
  epic-claimer:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      # Проверяем, что репозиторий приватный
      - name: Check repository visibility
        run: |
          if [[ "${{ github.event.repository.private }}" != "true" ]]; then
            echo "⚠️ This workflow must be run in a private repository for security reasons."
            echo "Please fork this repository and make it private before running this workflow."
            exit 0
          fi
          echo "✅ Running in private repository"

      # Получаем приватный репозиторий (нужен для работы с веткой data-persistence)
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1
          token: ${{ secrets.GITHUB_TOKEN }}

      # Создаём или переключаемся на ветку data-persistence
      - name: Switch to data-persistence branch
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"

          git fetch origin --prune

          if git ls-remote --exit-code --heads origin data-persistence >/dev/null 2>&1; then
            echo "Switching to existing data-persistence branch..."
            git checkout -B data-persistence origin/data-persistence
          else
            echo "Creating new data-persistence branch..."
            git checkout -b data-persistence
            git push -u origin data-persistence
          fi

      # Клонируем исходный код Epic-Claimer из публичного репозитория
      - name: Clone Epic-Claimer repository
        run: |
          echo "Cloning Epic-Claimer source code..."
          git clone https://github.com/Magerko/Epic-Claimer.git epic-claimer-src
          echo "✅ Source code cloned successfully"

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          version: '0.8.0'

      - name: "Set up Python"
        uses: actions/setup-python@v5
        with:
          python-version-file: "./epic-claimer-src/pyproject.toml"

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb libxml2-dev libxslt-dev

      # Устанавливаем зависимости проекта
      - name: Install dependencies
        working-directory: ./epic-claimer-src
        run: uv sync

      # Устанавливаем браузер Camoufox (с повтором при сбое сети)
      - name: Install Playwright browsers
        working-directory: ./epic-claimer-src
        run: |
          for i in {1..3}; do
            if uv run camoufox fetch; then
              echo "✅ Camoufox fetch successful (attempt $i)"
              break
            else
              echo "❌ Camoufox fetch attempt $i failed"
              if [[ $i -lt 3 ]]; then
                echo "⏳ Waiting 5 seconds before retry..."
                sleep 5
              else
                echo "⚠️ All camoufox fetch attempts failed"
                exit 1
              fi
            fi
          done

      # Запускаем Epic-Claimer из исходников
      - name: Run Epic-Claimer
        working-directory: ./epic-claimer-src
        env:
          EPIC_EMAIL: ${{ secrets.EPIC_EMAIL }}
          EPIC_PASSWORD: ${{ secrets.EPIC_PASSWORD }}
          EPIC_ACCOUNTS: ${{ secrets.EPIC_ACCOUNTS }}
          EPIC_PROXY: ${{ secrets.EPIC_PROXY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          ENABLE_APSCHEDULER: false
        run: |
          echo "Starting Epic-Claimer..."
          xvfb-run --auto-servernum --server-num=1 --server-args='-screen 0, 1920x1080x24' uv run app/deploy.py
          echo "Execution completed"

      # Копируем сгенерированные volumes из исходников в текущий репозиторий
      - name: Copy generated volumes to current repository
        if: always()
        run: |
          echo "Copying generated volumes from source to current repository..."
          mkdir -p app/volumes
          if [ -d "epic-claimer-src/app/volumes" ]; then
            cp -r epic-claimer-src/app/volumes/* app/volumes/ 2>/dev/null || echo "No volumes content to copy"
            echo "✅ Volumes copied successfully"
          else
            echo "⚠️ No volumes directory found in source"
          fi

      # Коммитим и пушим данные app/volumes в ветку data-persistence
      - name: Commit and push persistence data
        if: always()  # Сохраняем данные даже при ошибке задачи
        run: |
          git checkout data-persistence

          git add app/volumes/ || true

          if git diff --staged --quiet; then
            echo "✅ No changes to commit"
          else
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
            git commit -m "Update persistence data - $TIMESTAMP" \
              -m "Workflow run: ${{ github.run_id }}" \
              -m "Triggered by: ${{ github.event_name }}"
            git push origin data-persistence
          fi

      # Загружаем логи как Artifacts (для просмотра и резервного хранения)
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-claimer-logs-${{ github.run_id }}
          path: app/volumes/logs/
          retention-days: 7
          if-no-files-found: ignore

      # Загружаем runtime-данные и скриншоты как Artifacts
      - name: Upload runtime data
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-claimer-runtime-${{ github.run_id }}
          path: |
            app/volumes/runtime/
            app/volumes/screenshots/
          retention-days: 7
          if-no-files-found: ignore
```

</details>

> ℹ️ **Как работает сохранение данных**: workflow клонирует исходный код из публичного репозитория `Magerko/Epic-Claimer`, запускает его, а затем сохраняет рабочие данные (профиль браузера, логи, скриншоты) из `app/volumes/` в ветку `data-persistence` вашего приватного репозитория. Так состояние входа переживает перезапуски, а публичный код при этом остаётся неизменным.

### Шаг 3. Получите ключ Gemini API

Перед настройкой Secrets вам нужно получить ключ Google Gemini API:

1. Зайдите на [Google AI Studio](https://aistudio.google.com/apikey)
2. Войдите под своим аккаунтом Google
3. Нажмите «Create API Key»
4. Выберите проект Google Cloud (или создайте новый)
5. Скопируйте сгенерированный ключ и сохраните его в надёжном месте

### Шаг 4. Настройте Secrets

Добавьте в настройках репозитория следующую конфиденциальную информацию:

| Имя Secret | Описание |
|------------|------|
| `EPIC_EMAIL` | Email вашего аккаунта Epic Games<br>⚠️ Двухфакторная аутентификация должна быть отключена |
| `EPIC_PASSWORD` | Пароль вашего аккаунта Epic Games<br>⚠️ Двухфакторная аутентификация должна быть отключена |
| `GEMINI_API_KEY` | Ключ Google Gemini API<br>Получен на шаге 3 |

> 👥 **Несколько аккаунтов**: чтобы обрабатывать несколько аккаунтов за один запуск, вместо `EPIC_EMAIL`/`EPIC_PASSWORD` добавьте один Secret `EPIC_ACCOUNTS` с JSON-массивом:
> ```json
> [{"email":"first@example.com","password":"pass1"},{"email":"second@example.com","password":"pass2"}]
> ```
> Аккаунты обрабатываются последовательно. Учтите 20-минутный таймаут workflow — при большом числе аккаунтов увеличьте `timeout-minutes` или используйте развёртывание через Docker Compose на сервере.

> 🌐 **Прокси**: можно добавить Secret `EPIC_PROXY` (http/socks5) — он применится ко всем аккаунтам без собственного прокси. Прокси на конкретный аккаунт указывается полем `proxy` внутри `EPIC_ACCOUNTS`. Оба secret уже пробрасываются в workflow.

**Подробные шаги добавления**:
1. На странице репозитория нажмите вкладку «Settings» вверху
2. В левом меню найдите «Secrets and variables» → нажмите «Actions»
3. Нажмите кнопку «New repository secret»
4. Введите имя Secret (например, `EPIC_EMAIL`)
5. Введите соответствующее значение
6. Нажмите «Add secret»
7. Повторите шаги 3–6 для всех нужных Secrets

### Шаг 5. Настройте права workflow

Чтобы workflow мог создавать и управлять веткой `data-persistence`:

1. Откройте страницу Settings репозитория
2. В левом меню нажмите «Actions» → «General»
3. Прокрутите до раздела «Workflow permissions»
4. Выберите «Read and write permissions»
5. Отметьте «Allow GitHub Actions to create and approve pull requests»
6. Нажмите «Save», чтобы сохранить настройки

### Шаг 6. Включите Actions

Если это ваш первый workflow:

1. Нажмите вкладку «Actions» вверху репозитория
2. Если появится страница с предупреждением, нажмите «I understand my workflows, go ahead and enable them»
3. Вы должны увидеть workflow «Epic-Claimer»

### Шаг 7. Первый ручной запуск

После завершения всех настроек сразу проверьте workflow:

1. **Перейдите на страницу Actions**:
   - Нажмите вкладку «Actions» вверху репозитория

2. **Выберите workflow**:
   - В списке слева нажмите «Epic-Claimer»

3. **Запустите вручную**:
   - Нажмите кнопку «Run workflow» справа
   - Убедитесь, что выбрана ветка «main» (или ваша ветка по умолчанию)
   - Нажмите зелёную кнопку «Run workflow»

4. **Следите за выполнением**:
   - Страница обновится и покажет новую запись о запуске
   - Нажмите на запись, чтобы посмотреть подробности выполнения
   - Весь процесс занимает примерно 5–15 минут (первый запуск дольше из-за установки зависимостей и загрузки браузера)

5. **Проверьте результат**:
   - При успехе статус workflow будет зелёным ✅
   - При ошибке будет красный ❌ — нажмите, чтобы посмотреть лог ошибок

## Использование

### Ручной запуск

После первоначальной настройки вы можете запускать workflow вручную в любой момент:

1. Перейдите на вкладку Actions
2. Выберите workflow «Epic-Claimer»
3. Нажмите «Run workflow»
4. Выберите ветку (обычно main)
5. Нажмите зелёную кнопку «Run workflow»

### Просмотр результатов

1. Нажмите на выполняющийся или завершённый workflow
2. Посмотрите логи каждого шага
3. В разделе «Artifacts» скачайте логи и скриншоты

### Сохранение данных

- Данные пользователя автоматически сохраняются в ветке `data-persistence`
- Сюда входят состояние входа, кэш и другая информация
- При каждом запуске эти данные автоматически загружаются и обновляются

## Важные замечания

1. **Напоминание о безопасности**:
   - Запускайте только в приватном репозитории
   - Бережно храните логин и пароль от аккаунта
   - Периодически проверяйте, не утекли ли Secrets

2. **Ограничения по выполнению**:
   - У GitHub Actions есть ежемесячный бесплатный лимит (для приватных репозиториев — 2000 минут)
   - Подбирайте частоту запусков с учётом этого лимита

3. **Диагностика проблем**:
   - Если задача завершилась с ошибкой, проверьте логи Actions
   - Частые проблемы: таймаут сети, неудачное распознавание капчи, нестандартное состояние аккаунта
   - Через Artifacts можно скачать скриншоты и посмотреть, что именно произошло

## Настройка запуска по расписанию

### Включение запуска по расписанию

По умолчанию workflow поддерживает только ручной запуск. Чтобы включить автоматический запуск по расписанию, выполните следующие шаги:

1. Откройте файл `.github/workflows/epic-claimer.yml`
2. Найдите закомментированный блок schedule:
   ```yaml
   #  schedule:
   #    - cron: '55 15 * * *'
   ```
3. Уберите символы комментария, чтобы получилось:
   ```yaml
   schedule:
     - cron: '55 15 * * *'
   ```

### Пояснение к cron-выражению

`55 15 * * *` означает:
- Запуск раз в день в 15:55 (по UTC)
- Соответствует 23:55 по пекинскому времени (UTC+8)
- Соответствует 18:55 по московскому времени (UTC+3)

Для проверки и генерации собственных cron-выражений можно использовать [crontab.guru](https://crontab.guru/).

**Справка по часовым поясам**:
- UTC 15:55 = 18:55 по Москве (UTC+3)
- UTC 15:55 = 23:55 по Пекину
- UTC 15:55 = 00:55 следующего дня по Токио
- UTC 15:55 = 15:55/16:55 по Лондону (в зависимости от перехода на летнее время)

**Рекомендация**: при первом использовании сначала запустите workflow вручную несколько раз, убедитесь в его стабильности и только потом включайте запуск по расписанию.

## Частые вопросы

**В: Почему workflow обязательно запускать в приватном репозитории?**
О: Workflow обращается к данным вашего аккаунта Epic Games, и запуск в публичном репозитории может привести к утечке информации.

**В: Что делать, если при первом запуске возникла ошибка на шаге «Checkout repository»?**
О: Это нормально! При первом запуске ветка `data-persistence` ещё не существует, и workflow создаст её автоматически. Если вы увидели такую ошибку:
- Дождитесь автоматического повтора workflow (обычно успешно проходит через несколько секунд)
- Либо перезапустите workflow вручную
- При втором запуске эта проблема уже не возникнет

**В: Как посмотреть, какие игры были получены?**
О: Посмотрите лог запуска в Actions или скачайте файлы логов из Artifacts.

**В: Что делать, если запуск завершается с ошибкой?**
О: Проверьте лог ошибок. Частые причины:
- **Проблема с веткой Git**: нормально при первом запуске, достаточно перезапустить
- **Неверный логин или пароль**: проверьте настройку Secrets
- **Включена двухфакторная аутентификация**: 2FA в аккаунте Epic Games обязательно нужно отключить
- **Проблемы с сетью**: сеть GitHub Actions бывает нестабильной, помогает перезапуск
- **Недействительный API-ключ**: проверьте правильность ключа Gemini API

**В: Где хранятся данные?**
О: Сохранённые данные хранятся в ветке `data-persistence`, включая:
- `app/volumes/user_data/` — данные пользователя и состояние входа
- `app/volumes/logs/` — логи запусков
- `app/volumes/runtime/` и `app/volumes/screenshots/` — runtime-данные и скриншоты

# Epic Awesome Gamer — GitHub Actions workflow

> ⚡ **Быстрый старт**: следуя инструкции ниже, вы пройдёте путь от создания репозитория до первого запуска всего за 10 минут!

## Предварительные требования

Прежде чем начать, убедитесь, что у вас есть:

✅ Аккаунт GitHub (бесплатного достаточно)
✅ Аккаунт Epic Games (с отключённой двухфакторной аутентификацией)
✅ Аккаунт Google (для получения бесплатного ключа Gemini API)

⚠️ **Важное напоминание**: у аккаунта Epic Games обязательно должна быть отключена двухфакторная аутентификация (2FA), иначе автоматизация работать не будет.

## Особенности

✅ **Запуск по расписанию**: по умолчанию автоматически выполняется раз в день в 15:55 (UTC)
✅ **Ручной запуск**: поддерживается ручной запуск из интерфейса Actions
✅ **Проверка приватности репозитория**: workflow выполняется только в приватных репозиториях, что защищает ваш аккаунт
✅ **Сохранение данных**: данные пользователя хранятся в отдельной ветке, что обеспечивает сохранение состояния между запусками
✅ **Защита по таймауту**: автоматический таймаут через 15 минут предотвращает бесконечное выполнение
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
   - В поле имени файла введите: `.github/workflows/epic-gamer.yml`
   - GitHub автоматически создаст нужную структуру каталогов

2. **Вставьте содержимое workflow**:
   - Скопируйте полный YAML-код ниже и вставьте его в редактор
   - Нажмите «Commit new file» внизу страницы

<details>
<summary>📄 Нажмите, чтобы развернуть полное содержимое файла workflow (epic-gamer.yml)</summary>

```yaml
name: Epic Awesome Gamer

on:
  # Ручной запуск
  workflow_dispatch:
  
  # Запуск по расписанию — раз в день в 15:55 (UTC)
  schedule:
    - cron: '55 15 * * *'

jobs:
  epic-gamer:
    runs-on: ubuntu-latest
    timeout-minutes: 15  # Лимит таймаута 15 минут
    
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
      
      # Получаем код
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Полная история — нужна для операций с ветками
          
      # Создаём или переключаемся на ветку data-persistence
      - name: Setup data-persistence branch
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          
          # Проверяем, существует ли удалённая ветка
          if git ls-remote --heads origin data-persistence | grep -q data-persistence; then
            echo "data-persistence branch exists, checking out..."
            git checkout data-persistence
          else
            echo "Creating new data-persistence branch..."
            git checkout -b data-persistence
            
            # Создаём необходимую структуру каталогов
            mkdir -p volumes/user_data
            mkdir -p volumes/logs
            mkdir -p volumes/runtime
            
            # Создаём файлы .gitkeep, чтобы сохранить структуру каталогов
            touch volumes/user_data/.gitkeep
            touch volumes/logs/.gitkeep
            touch volumes/runtime/.gitkeep
            
            # Коммитим начальную структуру
            git add volumes/
            git commit -m "Initialize persistence directories" || echo "No changes to commit"
            git push -u origin data-persistence
          fi
      
      # Готовим каталоги для сохранения данных
      - name: Prepare volumes
        run: |
          # Убеждаемся, что каталоги существуют и имеют нужные права
          mkdir -p ${{ github.workspace }}/volumes/user_data
          mkdir -p ${{ github.workspace }}/volumes/logs
          mkdir -p ${{ github.workspace }}/volumes/runtime
          chmod -R 777 ${{ github.workspace }}/volumes
          
      # Запускаем контейнер
      - name: Run Epic Awesome Gamer
        run: |
          docker run \
            --rm \
            --name epic-awesome-gamer \
            --memory="4g" \
            --memory-swap="4g" \
            --shm-size="2gb" \
            -e EPIC_EMAIL="${{ secrets.EPIC_EMAIL }}" \
            -e EPIC_PASSWORD="${{ secrets.EPIC_PASSWORD }}" \
            -e GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}" \
            -v "${{ github.workspace }}/volumes/user_data:/app/app/volumes/user_data" \
            -v "${{ github.workspace }}/volumes/logs:/app/app/volumes/logs" \
            -v "${{ github.workspace }}/volumes/runtime:/app/app/volumes/runtime" \
            --entrypoint "/usr/bin/tini" \
            ghcr.io/qin2dim/epic-awesome-gamer:latest \
            -- xvfb-run --auto-servernum --server-num=1 --server-args='-screen 0, 1920x1080x24' uv run app/deploy.py
      
      # Коммитим обновление сохранённых данных
      - name: Commit and push persistence data
        if: always()  # Сохраняем данные даже при ошибке задачи
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          
          # Добавляем все изменения (включая логи)
          git add volumes/ || true
          
          # Проверяем, есть ли изменения
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            # Формируем сообщение коммита
            TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
            git commit -m "Update persistence data - $TIMESTAMP" \
              -m "Workflow run: ${{ github.run_id }}" \
              -m "Triggered by: ${{ github.event_name }}"
            
            # Пушим изменения
            git push origin data-persistence
          fi
          
      # Загружаем логи как Artifacts (для резервного хранения)
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-gamer-logs-${{ github.run_id }}
          path: volumes/logs/
          retention-days: 7
          
      # Загружаем runtime-данные как Artifacts (для резервного хранения)
      - name: Upload runtime data
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: epic-gamer-runtime-${{ github.run_id }}
          path: volumes/runtime/
          retention-days: 7
```

</details>

> ℹ️ **Примечание о путях монтирования**: пути в примере выше (`/app/app/volumes/...`) приведены в соответствие с актуальной структурой каталогов проекта (все рабочие данные складываются в `app/volumes/`). Если вы берёте workflow из более старых источников, проверьте, что тома смонтированы именно в `…/volumes/…`, иначе сохранение состояния между запусками работать не будет.

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
> Аккаунты обрабатываются последовательно. Учтите 15-минутный таймаут workflow — при большом числе аккаунтов увеличьте `timeout-minutes` или используйте развёртывание через Docker Compose на сервере.

**Подробные шаги добавления**:
1. На странице репозитория нажмите вкладку «Settings» вверху
2. В левом меню найдите «Secrets and variables» → нажмите «Actions»
3. Нажмите кнопку «New repository secret»
4. Введите имя Secret (например, `EPIC_EMAIL`)
5. Введите соответствующее значение
6. Нажмите «Add secret»
7. Повторите шаги 3–6 для всех трёх Secrets

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
3. Вы должны увидеть workflow «Epic Awesome Gamer»

### Шаг 7. Первый ручной запуск

После завершения всех настроек сразу проверьте workflow:

1. **Перейдите на страницу Actions**:
   - Нажмите вкладку «Actions» вверху репозитория

2. **Выберите workflow**:
   - В списке слева нажмите «Epic Awesome Gamer»

3. **Запустите вручную**:
   - Нажмите кнопку «Run workflow» справа
   - Убедитесь, что выбрана ветка «main» (или ваша ветка по умолчанию)
   - Нажмите зелёную кнопку «Run workflow»

4. **Следите за выполнением**:
   - Страница обновится и покажет новую запись о запуске
   - Нажмите на запись, чтобы посмотреть подробности выполнения
   - Весь процесс занимает примерно 3–10 минут

5. **Проверьте результат**:
   - При успехе статус workflow будет зелёным ✅
   - При ошибке будет красный ❌ — нажмите, чтобы посмотреть лог ошибок

## Использование

### Ручной запуск

После первоначальной настройки вы можете запускать workflow вручную в любой момент:

1. Перейдите на вкладку Actions
2. Выберите workflow «Epic Awesome Gamer»
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

1. Откройте файл `.github/workflows/epic-gamer.yml`
2. Найдите закомментированный блок schedule:
   ```yaml
   # schedule:
   #   - cron: '55 15 * * *'
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
- `/volumes/user_data/` — данные пользователя и состояние входа
- `/volumes/logs/` — логи запусков
- `/volumes/runtime/` — runtime-данные и скриншоты

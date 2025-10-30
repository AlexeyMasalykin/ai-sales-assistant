# Структура тестов

## Unit-тесты (`tests/unit/`)
- Быстрые тесты с моками
- Не требуют секретов или внешних API
- Должны всегда проходить локально и в CI

**Запуск:**
```bash
pytest tests/unit/
```

## Integration-тесты (`tests/integration/`)
- Работают с реальными API (Avito, Telegram, RAG и др.)
- Требуют настроенных секретов в `.env`
- Автоматически пропускаются, если секреты отсутствуют

**Запуск всех integration тестов:**
```bash
pytest tests/integration/
```

**Перед запуском убедитесь, что .env содержит:**
```env
AVITO_CLIENT_ID=...
AVITO_CLIENT_SECRET=...
TELEGRAM_BOT_TOKEN=...
```

## Маркеры
- `@pytest.mark.unit` — unit-тест
- `@pytest.mark.integration` — интеграционный тест
- `@skip_without_avito` — пропуск теста без Avito секретов
- `@skip_without_telegram` — пропуск теста без Telegram токена

## Примеры

### Unit-тест (всегда запускается)
```python
@pytest.mark.unit
async def test_format_message(mock_redis):
    ...
```

### Integration-тест (требует секреты)
```python
from tests.conftest import skip_without_avito

@skip_without_avito
@pytest.mark.integration
async def test_real_avito_oauth():
    ...
```

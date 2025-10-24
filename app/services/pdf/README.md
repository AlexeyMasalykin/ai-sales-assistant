# PDF Generator Module

Модуль для генерации PDF документов из HTML с использованием WeasyPrint.

## Возможности

- ✅ Конвертация HTML в PDF с поддержкой CSS
- ✅ Контроль размера файла (максимум 10 МБ по умолчанию)
- ✅ Автоматическое сохранение с временными метками
- ✅ Санитизация имён файлов
- ✅ Поддержка кириллицы и Unicode
- ✅ Многостраничные документы
- ✅ Пользовательские стили для печати

## Использование

### Базовая генерация PDF

```python
from app.services.pdf.generator import pdf_generator

# Простая конвертация HTML в PDF
html = "<html><body><h1>Hello World</h1></body></html>"
pdf_bytes = pdf_generator.html_to_pdf(html)

# Сохранение в файл
file_path = pdf_generator.save_pdf(html, "my_document")
```

### Генерация с пользовательскими стилями

```python
html = "<html><body><h1>Styled Document</h1></body></html>"
css = "h1 { color: red; font-size: 24pt; }"

pdf_bytes = pdf_generator.html_to_pdf(html, css=css)
```

### Генерация с автоматическим именованием

```python
html = "<html><body><h1>Commercial Proposal</h1></body></html>"

pdf_bytes, file_path = pdf_generator.generate_with_template(
    html,
    document_type="commercial_proposal",
    client_name="ООО Компания",
    save_to_disk=True
)

# Файл будет сохранён как: commercial_proposal_Компания_20241024_123456.pdf
```

### Интеграция с Document Generator

```python
from app.services.documents.generator import document_generator

# Генерация прайс-листа в PDF
pdf_bytes, file_path = await document_generator.generate_price_list_pdf(
    client_name="ООО Клиент",
    services=["AI Ассистент", "Автоматизация"]
)

# Генерация коммерческого предложения в PDF
pdf_bytes, file_path = await document_generator.generate_commercial_proposal_pdf({
    "name": "Иван Иванов",
    "company": "ООО Инновации",
    "services": "AI автоматизация"
})

# Генерация договора в PDF
pdf_bytes, file_path = await document_generator.generate_contract_draft_pdf({
    "name": "ООО Клиент",
    "inn": "1234567890",
    "services": "Разработка AI-ассистента"
})
```

## Настройки

В `app/core/settings.py`:

```python
# Максимальный размер PDF в мегабайтах
max_pdf_size_mb: int = 10

# Директория для сохранения PDF
pdf_output_dir: str = "data/documents"
```

Переменные окружения (.env):

```bash
MAX_PDF_SIZE_MB=10
PDF_OUTPUT_DIR=data/documents
```

## Обработка ошибок

```python
from app.services.pdf.generator import pdf_generator, PDFSizeExceededException

try:
    pdf_bytes = pdf_generator.html_to_pdf(large_html)
except PDFSizeExceededException as e:
    print(f"PDF слишком большой: {e}")
except Exception as e:
    print(f"Ошибка генерации PDF: {e}")
```

## Информация о PDF

```python
pdf_bytes = pdf_generator.html_to_pdf(html)
info = pdf_generator.get_pdf_info(pdf_bytes)

print(f"Размер: {info['size_mb']} МБ")
print(f"В пределах лимита: {info['within_limit']}")
```

## Тестирование

Unit-тесты: `tests/unit/test_pdf_generator.py`
```bash
pytest tests/unit/test_pdf_generator.py -v
```

Интеграционные тесты: `tests/integration/test_pdf_generation.py`
```bash
pytest tests/integration/test_pdf_generation.py -v
```

## Структура модуля

```
app/services/pdf/
├── __init__.py          # Экспорт публичного API
├── generator.py         # Основной класс PDFGenerator
└── README.md           # Документация (этот файл)
```

## Зависимости

- `weasyprint>=60.0` - библиотека для конвертации HTML в PDF
- `loguru` - логирование
- `pydantic-settings` - настройки приложения

## Примечания

- WeasyPrint требует системных библиотек для рендеринга (cairo, pango)
- PDF файлы сохраняются в директорию `data/documents/`
- Имена файлов автоматически получают временную метку
- Специальные символы в именах клиентов санитизируются
- Поддерживается полный набор CSS для стилизации документов


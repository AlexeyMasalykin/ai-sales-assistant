"""Генератор PDF документов через WeasyPrint."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from weasyprint import HTML, CSS

from app.core.settings import settings


class PDFSizeExceededException(Exception):
    """Исключение при превышении максимального размера PDF."""
    pass


class PDFGenerator:
    """Генератор PDF документов с контролем размера."""

    def __init__(self) -> None:
        self.max_size_mb = settings.max_pdf_size_mb
        self.output_dir = Path(settings.pdf_output_dir)
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Создаёт директорию для выходных файлов, если её нет."""
        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Создана директория для PDF: %s", self.output_dir)

    def html_to_pdf(
        self,
        html_content: str,
        css: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> bytes:
        """
        Конвертирует HTML в PDF.

        Args:
            html_content: HTML-контент для конвертации
            css: Дополнительные CSS-стили (опционально)
            base_url: Базовый URL для разрешения относительных путей

        Returns:
            PDF в виде байтов

        Raises:
            PDFSizeExceededException: Если размер PDF превышает лимит
        """
        logger.info("Начало генерации PDF из HTML (%d символов)", len(html_content))

        try:
            # Создаём объект HTML
            html = HTML(string=html_content, base_url=base_url)

            # Применяем дополнительные стили, если есть
            stylesheets = []
            if css:
                stylesheets.append(CSS(string=css))

            # Генерируем PDF в память
            pdf_buffer = io.BytesIO()
            html.write_pdf(pdf_buffer, stylesheets=stylesheets)
            pdf_bytes = pdf_buffer.getvalue()

            # Проверяем размер
            pdf_size_mb = len(pdf_bytes) / (1024 * 1024)
            logger.info("PDF сгенерирован, размер: %.2f МБ", pdf_size_mb)

            if pdf_size_mb > self.max_size_mb:
                error_msg = (
                    f"Размер PDF ({pdf_size_mb:.2f} МБ) превышает "
                    f"максимальный лимит ({self.max_size_mb} МБ)"
                )
                logger.error(error_msg)
                raise PDFSizeExceededException(error_msg)

            return pdf_bytes

        except PDFSizeExceededException:
            raise
        except Exception as exc:
            logger.error("Ошибка генерации PDF: %s", exc)
            raise

    def save_pdf(
        self,
        html_content: str,
        filename: str,
        css: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Path:
        """
        Генерирует PDF и сохраняет в файл.

        Args:
            html_content: HTML-контент
            filename: Имя файла (без расширения .pdf)
            css: Дополнительные CSS-стили
            base_url: Базовый URL

        Returns:
            Путь к сохранённому файлу
        """
        # Генерируем PDF
        pdf_bytes = self.html_to_pdf(html_content, css=css, base_url=base_url)

        # Формируем имя файла с временной меткой
        if not filename.endswith(".pdf"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename}_{timestamp}.pdf"

        # Сохраняем файл
        file_path = self.output_dir / filename
        file_path.write_bytes(pdf_bytes)

        logger.info("PDF сохранён: %s (%.2f МБ)", file_path, len(pdf_bytes) / (1024 * 1024))
        return file_path

    def generate_with_template(
        self,
        html_content: str,
        document_type: str,
        client_name: str,
        save_to_disk: bool = True,
    ) -> tuple[bytes, Optional[Path]]:
        """
        Генерирует PDF с автоматическим именованием.

        Args:
            html_content: HTML-контент
            document_type: Тип документа (proposal, contract, invoice, price_list)
            client_name: Имя клиента для имени файла
            save_to_disk: Сохранять ли на диск

        Returns:
            Кортеж (PDF в байтах, путь к файлу или None)
        """
        # Добавляем базовые стили для печати
        base_css = """
            @page {
                size: A4;
                margin: 2cm;
            }
            body {
                font-family: 'DejaVu Sans', Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }
            h1 { font-size: 20pt; color: #1a1a1a; }
            h2 { font-size: 16pt; color: #2a2a2a; }
            h3 { font-size: 14pt; color: #3a3a3a; }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 1em 0;
            }
            table th, table td {
                padding: 8px;
                border: 1px solid #ddd;
                text-align: left;
            }
            table th {
                background-color: #f5f5f5;
                font-weight: bold;
            }
        """

        # Генерируем PDF
        pdf_bytes = self.html_to_pdf(html_content, css=base_css)

        # Сохраняем на диск, если требуется
        file_path = None
        if save_to_disk:
            # Формируем имя файла
            safe_client_name = "".join(
                c for c in client_name if c.isalnum() or c in (" ", "_", "-")
            ).strip()
            safe_client_name = safe_client_name.replace(" ", "_")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{document_type}_{safe_client_name}_{timestamp}.pdf"

            file_path = self.output_dir / filename
            file_path.write_bytes(pdf_bytes)
            
            logger.info(
                "PDF документ '%s' для клиента '%s' сохранён: %s",
                document_type,
                client_name,
                file_path,
            )

        return pdf_bytes, file_path

    def get_pdf_info(self, pdf_bytes: bytes) -> dict:
        """
        Возвращает информацию о PDF.

        Args:
            pdf_bytes: PDF в байтах

        Returns:
            Словарь с информацией (размер в байтах и МБ)
        """
        size_bytes = len(pdf_bytes)
        size_mb = size_bytes / (1024 * 1024)
        
        return {
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 2),
            "within_limit": size_mb <= self.max_size_mb,
            "max_size_mb": self.max_size_mb,
        }


# Singleton
pdf_generator = PDFGenerator()


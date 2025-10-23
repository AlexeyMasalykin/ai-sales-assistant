"""Менеджер шаблонов документов."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader, Template
from loguru import logger


class TemplateManager:
    """Менеджер шаблонов для генерации документов"""

    def __init__(self) -> None:
        self.templates_path = Path("documents/knowledge_base/documents/templates")
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_path)), autoescape=True
        )

    def get_template(self, template_name: str) -> Template:
        """Получает шаблон по имени"""
        try:
            template = self.env.get_template(template_name)
            logger.debug("Шаблон %s загружен", template_name)
            return template
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка загрузки шаблона %s: %s", template_name, exc)
            raise

    def render_template(self, template_name: str, context: Dict) -> str:
        """Рендерит шаблон с контекстом"""
        template = self.get_template(template_name)

        try:
            rendered = template.render(**context)
            logger.info("Шаблон %s отрендерен", template_name)
            return rendered
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка рендеринга шаблона %s: %s", template_name, exc)
            raise

    def list_templates(self) -> list[str]:
        """Список доступных шаблонов"""
        if not self.templates_path.exists():
            return []

        templates = [f.name for f in self.templates_path.glob("*.html")]

        logger.debug("Найдено %s шаблонов", len(templates))
        return templates


# Singleton
template_manager = TemplateManager()

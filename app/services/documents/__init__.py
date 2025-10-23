"""Сервис генерации документов."""

from app.services.documents.generator import DocumentGenerator, document_generator
from app.services.documents.templates import TemplateManager, template_manager

__all__ = [
    "DocumentGenerator",
    "document_generator",
    "TemplateManager",
    "template_manager",
]

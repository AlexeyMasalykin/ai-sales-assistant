"""Загрузчик промптов из .poml файлов."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


class PromptLoader:
    """Загружает и кэширует промпты из .poml файлов."""

    def __init__(self, prompts_dir: str | Path):
        self.prompts_dir = Path(prompts_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    def load_file(self, filename: str) -> dict[str, Any]:
        """Загрузить .poml файл."""
        if filename in self._cache:
            return self._cache[filename]

        file_path = self.prompts_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Промпт файл не найден: {file_path}")

        with open(file_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        self._cache[filename] = data
        logger.debug(f"Загружен промпт файл: {filename}")
        return data

    def get_prompt(
        self,
        file: str,
        prompt_key: str,
        **template_vars: Any,
    ) -> tuple[str, str]:
        """
        Получить system и user промпты с подстановкой переменных.

        Returns:
            (system_prompt, user_prompt)
        """
        data = self.load_file(file)
        
        # Промпты находятся либо в секции "prompts", либо на верхнем уровне
        # (игнорируем мета-поля: version, model)
        prompts = data.get("prompts", data)
        
        # Фильтруем мета-поля, если промпты на верхнем уровне
        meta_fields = {"version", "model"}
        if prompts is data:
            prompts = {k: v for k, v in data.items() if k not in meta_fields}

        if prompt_key not in prompts:
            available = ", ".join(prompts.keys())
            raise KeyError(
                f"Промпт '{prompt_key}' не найден в {file}. "
                f"Доступные промпты: {available}"
            )

        prompt_data = prompts[prompt_key]
        system = prompt_data.get("system", "")
        user_template = prompt_data.get("user_template", "")

        # Безопасная подстановка переменных (только те, что есть в template_vars)
        system = self._safe_format(system, template_vars)
        user = self._safe_format(user_template, template_vars)

        return system, user
    
    def _safe_format(self, template: str, vars: dict[str, Any]) -> str:
        """
        Безопасная подстановка переменных.
        Заменяет только {variable}, которые есть в vars.
        Остальные фигурные скобки остаются как есть.
        """
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name in vars:
                return str(vars[var_name])
            # Возвращаем оригинальную строку, если переменной нет
            return match.group(0)
        
        # Ищем {variable_name} и заменяем только известные переменные
        return re.sub(r"\{([^{}]+)\}", replace_var, template)

"""Правила ценообразования для AI-решений."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProductType(str, Enum):
    """Типы продуктов."""

    AI_MANAGER = "ai_manager"
    AI_LAWYER = "ai_lawyer"
    AI_ANALYST = "ai_analyst"


class ServiceType(str, Enum):
    """Типы дополнительных услуг."""

    IMPLEMENTATION = "implementation"
    CRM_INTEGRATION = "crm_integration"
    TRAINING = "training"
    CUSTOMIZATION = "customization"


@dataclass(frozen=True)
class TariffPlan:
    """Тарифный план."""

    name: str
    product: ProductType
    price_monthly: int
    users_limit: int | None
    features: list[str]
    is_enterprise: bool = False


@dataclass(frozen=True)
class AdditionalService:
    """Дополнительная услуга."""

    service_type: ServiceType
    name: str
    price: int
    unit: str


@dataclass(frozen=True)
class PackageDiscount:
    """Пакетная скидка."""

    name: str
    products: list[ProductType]
    discount_percent: int
    min_price: int


AI_MANAGER_TARIFFS: list[TariffPlan] = [
    TariffPlan(
        name="Старт",
        product=ProductType.AI_MANAGER,
        price_monthly=80_000,
        users_limit=5,
        features=["Базовые функции"],
    ),
    TariffPlan(
        name="Бизнес",
        product=ProductType.AI_MANAGER,
        price_monthly=150_000,
        users_limit=20,
        features=["Полный функционал"],
    ),
    TariffPlan(
        name="Корпорация",
        product=ProductType.AI_MANAGER,
        price_monthly=320_000,
        users_limit=100,
        features=["Полный функционал", "API"],
    ),
    TariffPlan(
        name="Энтерпрайз",
        product=ProductType.AI_MANAGER,
        price_monthly=0,
        users_limit=None,
        features=["Всё", "Кастомизация"],
        is_enterprise=True,
    ),
]


AI_LAWYER_TARIFFS: list[TariffPlan] = [
    TariffPlan(
        name="Соло",
        product=ProductType.AI_LAWYER,
        price_monthly=50_000,
        users_limit=1,
        features=["500 документов/мес"],
    ),
    TariffPlan(
        name="Команда",
        product=ProductType.AI_LAWYER,
        price_monthly=100_000,
        users_limit=5,
        features=["2,500 документов/мес"],
    ),
    TariffPlan(
        name="Департамент",
        product=ProductType.AI_LAWYER,
        price_monthly=200_000,
        users_limit=20,
        features=["10,000 документов/мес"],
    ),
    TariffPlan(
        name="Корпорация",
        product=ProductType.AI_LAWYER,
        price_monthly=350_000,
        users_limit=None,
        features=["Безлимит документов"],
    ),
]


AI_ANALYST_TARIFFS: list[TariffPlan] = [
    TariffPlan(
        name="Лайт",
        product=ProductType.AI_ANALYST,
        price_monthly=60_000,
        users_limit=None,
        features=["до 1 млн строк", "5 дашбордов", "2 модели ML"],
    ),
    TariffPlan(
        name="Стандарт",
        product=ProductType.AI_ANALYST,
        price_monthly=120_000,
        users_limit=None,
        features=["до 10 млн строк", "20 дашбордов", "5 моделей ML"],
    ),
    TariffPlan(
        name="Про",
        product=ProductType.AI_ANALYST,
        price_monthly=250_000,
        users_limit=None,
        features=["до 100 млн строк", "50 дашбордов", "10 моделей ML"],
    ),
    TariffPlan(
        name="Энтерпрайз",
        product=ProductType.AI_ANALYST,
        price_monthly=0,
        users_limit=None,
        features=["Безлимит"],
        is_enterprise=True,
    ),
]


ADDITIONAL_SERVICES: list[AdditionalService] = [
    AdditionalService(
        service_type=ServiceType.IMPLEMENTATION,
        name="Внедрение",
        price=80_000,
        unit="от (разово)",
    ),
    AdditionalService(
        service_type=ServiceType.CRM_INTEGRATION,
        name="Интеграция с CRM",
        price=30_000,
        unit="разово",
    ),
    AdditionalService(
        service_type=ServiceType.TRAINING,
        name="Обучение сотрудников",
        price=15_000,
        unit="день",
    ),
    AdditionalService(
        service_type=ServiceType.CUSTOMIZATION,
        name="Кастомизация",
        price=50_000,
        unit="от/модуль",
    ),
]


PACKAGE_DISCOUNTS: list[PackageDiscount] = [
    PackageDiscount(
        name="Цифровой офис",
        products=[ProductType.AI_MANAGER, ProductType.AI_LAWYER],
        discount_percent=15,
        min_price=200_000,
    ),
    PackageDiscount(
        name="Умный бизнес",
        products=[ProductType.AI_MANAGER, ProductType.AI_ANALYST],
        discount_percent=15,
        min_price=220_000,
    ),
    PackageDiscount(
        name="Полная автоматизация",
        products=[
            ProductType.AI_MANAGER,
            ProductType.AI_LAWYER,
            ProductType.AI_ANALYST,
        ],
        discount_percent=20,
        min_price=350_000,
    ),
]


ANNUAL_PAYMENT_DISCOUNT = 15
STARTUP_NGO_DISCOUNT = 20


def get_all_tariffs() -> dict[ProductType, list[TariffPlan]]:
    """Возвращает все тарифы, сгруппированные по продуктам."""
    return {
        ProductType.AI_MANAGER: AI_MANAGER_TARIFFS,
        ProductType.AI_LAWYER: AI_LAWYER_TARIFFS,
        ProductType.AI_ANALYST: AI_ANALYST_TARIFFS,
    }

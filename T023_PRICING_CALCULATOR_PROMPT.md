ЗАДАЧА T023: Сервис расчёта стоимости AI-решений

⚠️ ВАЖНО: НЕ ТРОГАЙ .env ФАЙЛ!

КОНТЕКСТ:
- T021-T022 завершены ✅
- RAG система работает
- Документы с ценами загружены в базу знаний
- Генерация документов частично реализована
- Нужен автоматический расчёт стоимости для КП

ЦЕЛЬ T023:
Создать сервис автоматического расчёта стоимости AI-решений с учётом тарифов, скидок и дополнительных услуг

ПРОБЛЕМА СЕЙЧАС:
- Цены есть только в markdown документах
- Нет программного способа рассчитать стоимость
- КП генерируются без автоматического расчёта
- Скидки применяются вручную

РЕШЕНИЕ:
Создать PricingCalculator с правилами расчёта и конфигурацией тарифов

СОЗДАТЬ ФАЙЛЫ:

1. app/core/pricing_rules.py (НОВЫЙ)
   Конфигурация тарифов и правил:
```python
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
    IMPLEMENTATION = "implementation"  # Внедрение
    CRM_INTEGRATION = "crm_integration"  # Интеграция с CRM
    TRAINING = "training"  # Обучение
    CUSTOMIZATION = "customization"  # Кастомизация


@dataclass
class TariffPlan:
    """Тарифный план."""
    name: str
    product: ProductType
    price_monthly: int  # Цена в рублях
    users_limit: int | None  # None = безлимит
    features: list[str]
    is_enterprise: bool = False


@dataclass
class AdditionalService:
    """Дополнительная услуга."""
    service_type: ServiceType
    name: str
    price: int  # Цена в рублях
    unit: str  # Единица измерения (разово, день, модуль)


@dataclass
class PackageDiscount:
    """Пакетная скидка."""
    name: str
    products: list[ProductType]
    discount_percent: int
    min_price: int  # Минимальная цена пакета


# ============================================================================
# ТАРИФЫ AI-MANAGER
# ============================================================================

AI_MANAGER_TARIFFS = [
    TariffPlan(
        name="Старт",
        product=ProductType.AI_MANAGER,
        price_monthly=80_000,
        users_limit=5,
        features=["Базовые функции"]
    ),
    TariffPlan(
        name="Бизнес",
        product=ProductType.AI_MANAGER,
        price_monthly=150_000,
        users_limit=20,
        features=["Полный функционал"]
    ),
    TariffPlan(
        name="Корпорация",
        product=ProductType.AI_MANAGER,
        price_monthly=320_000,
        users_limit=100,
        features=["Полный функционал", "API"]
    ),
    TariffPlan(
        name="Энтерпрайз",
        product=ProductType.AI_MANAGER,
        price_monthly=0,  # Индивидуально
        users_limit=None,
        features=["Всё", "Кастомизация"],
        is_enterprise=True
    ),
]

# ============================================================================
# ТАРИФЫ AI-LAWYER
# ============================================================================

AI_LAWYER_TARIFFS = [
    TariffPlan(
        name="Соло",
        product=ProductType.AI_LAWYER,
        price_monthly=50_000,
        users_limit=1,
        features=["500 документов/мес"]
    ),
    TariffPlan(
        name="Команда",
        product=ProductType.AI_LAWYER,
        price_monthly=100_000,
        users_limit=5,
        features=["2,500 документов/мес"]
    ),
    TariffPlan(
        name="Департамент",
        product=ProductType.AI_LAWYER,
        price_monthly=200_000,
        users_limit=20,
        features=["10,000 документов/мес"]
    ),
    TariffPlan(
        name="Корпорация",
        product=ProductType.AI_LAWYER,
        price_monthly=350_000,
        users_limit=None,
        features=["Безлимит документов"],
        is_enterprise=False
    ),
]

# ============================================================================
# ТАРИФЫ AI-ANALYST
# ============================================================================

AI_ANALYST_TARIFFS = [
    TariffPlan(
        name="Лайт",
        product=ProductType.AI_ANALYST,
        price_monthly=60_000,
        users_limit=None,
        features=["до 1 млн строк", "5 дашбордов", "2 модели ML"]
    ),
    TariffPlan(
        name="Стандарт",
        product=ProductType.AI_ANALYST,
        price_monthly=120_000,
        users_limit=None,
        features=["до 10 млн строк", "20 дашбордов", "5 моделей ML"]
    ),
    TariffPlan(
        name="Про",
        product=ProductType.AI_ANALYST,
        price_monthly=250_000,
        users_limit=None,
        features=["до 100 млн строк", "50 дашбордов", "10 моделей ML"]
    ),
    TariffPlan(
        name="Энтерпрайз",
        product=ProductType.AI_ANALYST,
        price_monthly=0,
        users_limit=None,
        features=["Безлимит"],
        is_enterprise=True
    ),
]

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ
# ============================================================================

ADDITIONAL_SERVICES = [
    AdditionalService(
        service_type=ServiceType.IMPLEMENTATION,
        name="Внедрение",
        price=80_000,
        unit="от (разово)"
    ),
    AdditionalService(
        service_type=ServiceType.CRM_INTEGRATION,
        name="Интеграция с CRM",
        price=30_000,
        unit="разово"
    ),
    AdditionalService(
        service_type=ServiceType.TRAINING,
        name="Обучение сотрудников",
        price=15_000,
        unit="день"
    ),
    AdditionalService(
        service_type=ServiceType.CUSTOMIZATION,
        name="Кастомизация",
        price=50_000,
        unit="от/модуль"
    ),
]

# ============================================================================
# ПАКЕТНЫЕ ПРЕДЛОЖЕНИЯ
# ============================================================================

PACKAGE_DISCOUNTS = [
    PackageDiscount(
        name="Цифровой офис",
        products=[ProductType.AI_MANAGER, ProductType.AI_LAWYER],
        discount_percent=15,
        min_price=200_000
    ),
    PackageDiscount(
        name="Умный бизнес",
        products=[ProductType.AI_MANAGER, ProductType.AI_ANALYST],
        discount_percent=15,
        min_price=220_000
    ),
    PackageDiscount(
        name="Полная автоматизация",
        products=[ProductType.AI_MANAGER, ProductType.AI_LAWYER, ProductType.AI_ANALYST],
        discount_percent=20,
        min_price=350_000
    ),
]

# ============================================================================
# СКИДКИ
# ============================================================================

# Скидка за годовую оплату
ANNUAL_PAYMENT_DISCOUNT = 15

# Скидка для стартапов и НКО
STARTUP_NGO_DISCOUNT = 20


def get_all_tariffs() -> dict[ProductType, list[TariffPlan]]:
    """Возвращает все тарифы, сгруппированные по продуктам."""
    return {
        ProductType.AI_MANAGER: AI_MANAGER_TARIFFS,
        ProductType.AI_LAWYER: AI_LAWYER_TARIFFS,
        ProductType.AI_ANALYST: AI_ANALYST_TARIFFS,
    }
```

2. app/services/pricing/calculator.py (НОВЫЙ)
   Сервис расчёта стоимости:
```python
"""Сервис расчёта стоимости AI-решений."""

from __future__ import annotations

from dataclasses import dataclass
from loguru import logger

from app.core.pricing_rules import (
    ProductType,
    ServiceType,
    TariffPlan,
    AdditionalService,
    PackageDiscount,
    get_all_tariffs,
    ADDITIONAL_SERVICES,
    PACKAGE_DISCOUNTS,
    ANNUAL_PAYMENT_DISCOUNT,
    STARTUP_NGO_DISCOUNT,
)


@dataclass
class SelectedProduct:
    """Выбранный продукт с тарифом."""
    product: ProductType
    tariff: TariffPlan
    months: int = 12  # Срок подписки


@dataclass
class SelectedService:
    """Выбранная дополнительная услуга."""
    service: AdditionalService
    quantity: int = 1  # Количество (дней обучения, модулей и т.д.)


@dataclass
class PricingResult:
    """Результат расчёта стоимости."""
    products: list[SelectedProduct]
    services: list[SelectedService]
    
    # Расчёты
    products_subtotal: int  # Сумма за продукты (без скидок)
    services_subtotal: int  # Сумма за услуги
    
    # Скидки
    package_discount_name: str | None
    package_discount_percent: int
    package_discount_amount: int
    
    annual_discount_applied: bool
    annual_discount_amount: int
    
    startup_discount_applied: bool
    startup_discount_amount: int
    
    # Итого
    total_discount_amount: int
    total_monthly: int  # Ежемесячный платёж
    total_annual: int  # Годовой платёж
    total_with_services: int  # Общая сумма с услугами
    
    def format_summary(self) -> str:
        """Форматирует краткую сводку."""
        lines = []
        lines.append("💰 РАСЧЁТ СТОИМОСТИ")
        lines.append("")
        
        # Продукты
        lines.append("📦 Продукты:")
        for sp in self.products:
            lines.append(f"  • {sp.product.value} ({sp.tariff.name}): {sp.tariff.price_monthly:,}₽/мес × {sp.months} мес")
        lines.append(f"Итого за продукты: {self.products_subtotal:,}₽")
        lines.append("")
        
        # Услуги
        if self.services:
            lines.append("🛠 Дополнительные услуги:")
            for ss in self.services:
                lines.append(f"  • {ss.service.name}: {ss.service.price:,}₽ × {ss.quantity}")
            lines.append(f"Итого за услуги: {self.services_subtotal:,}₽")
            lines.append("")
        
        # Скидки
        if self.total_discount_amount > 0:
            lines.append("🎁 Скидки:")
            if self.package_discount_amount > 0:
                lines.append(f"  • Пакет '{self.package_discount_name}': -{self.package_discount_percent}% ({self.package_discount_amount:,}₽)")
            if self.annual_discount_amount > 0:
                lines.append(f"  • Годовая оплата: -{ANNUAL_PAYMENT_DISCOUNT}% ({self.annual_discount_amount:,}₽)")
            if self.startup_discount_amount > 0:
                lines.append(f"  • Стартап/НКО: -{STARTUP_NGO_DISCOUNT}% ({self.startup_discount_amount:,}₽)")
            lines.append(f"Всего скидка: {self.total_discount_amount:,}₽")
            lines.append("")
        
        # Итого
        lines.append("💵 ИТОГО:")
        lines.append(f"Ежемесячно: {self.total_monthly:,}₽")
        lines.append(f"За год: {self.total_annual:,}₽")
        if self.services:
            lines.append(f"С услугами: {self.total_with_services:,}₽")
        
        return "\n".join(lines)


class PricingCalculator:
    """Калькулятор стоимости AI-решений."""
    
    def __init__(self):
        self.all_tariffs = get_all_tariffs()
        self.services = {s.service_type: s for s in ADDITIONAL_SERVICES}
        self.packages = PACKAGE_DISCOUNTS
    
    def find_tariff(
        self,
        product: ProductType,
        tariff_name: str
    ) -> TariffPlan | None:
        """Находит тариф по названию."""
        tariffs = self.all_tariffs.get(product, [])
        for tariff in tariffs:
            if tariff.name.lower() == tariff_name.lower():
                return tariff
        return None
    
    def find_tariff_by_users(
        self,
        product: ProductType,
        users_count: int
    ) -> TariffPlan | None:
        """Подбирает тариф по количеству пользователей."""
        tariffs = self.all_tariffs.get(product, [])
        
        # Ищем подходящий тариф
        for tariff in sorted(tariffs, key=lambda t: t.price_monthly):
            if tariff.is_enterprise:
                continue
            if tariff.users_limit is None or users_count <= tariff.users_limit:
                return tariff
        
        # Если не нашли - возвращаем энтерпрайз
        for tariff in tariffs:
            if tariff.is_enterprise:
                return tariff
        
        return None
    
    def get_service(self, service_type: ServiceType) -> AdditionalService | None:
        """Получает услугу по типу."""
        return self.services.get(service_type)
    
    def calculate(
        self,
        products: list[SelectedProduct],
        services: list[SelectedService] | None = None,
        apply_annual_discount: bool = False,
        apply_startup_discount: bool = False
    ) -> PricingResult:
        """Рассчитывает стоимость."""
        logger.info(
            "Расчёт стоимости: продуктов=%d, услуг=%d",
            len(products),
            len(services) if services else 0
        )
        
        services = services or []
        
        # Проверяем энтерпрайз тарифы
        has_enterprise = any(p.tariff.is_enterprise for p in products)
        if has_enterprise:
            logger.warning("Обнаружен энтерпрайз тариф - требуется индивидуальный расчёт")
        
        # 1. Считаем базовую стоимость продуктов
        products_subtotal = sum(
            p.tariff.price_monthly * p.months for p in products
            if not p.tariff.is_enterprise
        )
        
        # 2. Считаем услуги
        services_subtotal = sum(
            s.service.price * s.quantity for s in services
        )
        
        # 3. Проверяем пакетную скидку
        selected_products = {p.product for p in products}
        package_discount = self._find_package_discount(selected_products)
        
        package_discount_name = None
        package_discount_percent = 0
        package_discount_amount = 0
        
        if package_discount:
            package_discount_name = package_discount.name
            package_discount_percent = package_discount.discount_percent
            package_discount_amount = int(products_subtotal * package_discount_percent / 100)
            logger.info(
                "Применена пакетная скидка '%s': %d%% (-%d₽)",
                package_discount_name,
                package_discount_percent,
                package_discount_amount
            )
        
        # 4. Годовая скидка (применяется после пакетной)
        annual_discount_applied = apply_annual_discount
        annual_discount_amount = 0
        
        if apply_annual_discount:
            base_after_package = products_subtotal - package_discount_amount
            annual_discount_amount = int(base_after_package * ANNUAL_PAYMENT_DISCOUNT / 100)
            logger.info("Применена скидка за годовую оплату: %d%% (-%d₽)", ANNUAL_PAYMENT_DISCOUNT, annual_discount_amount)
        
        # 5. Скидка для стартапов (применяется последней)
        startup_discount_applied = apply_startup_discount
        startup_discount_amount = 0
        
        if apply_startup_discount:
            base_after_all = products_subtotal - package_discount_amount - annual_discount_amount
            startup_discount_amount = int(base_after_all * STARTUP_NGO_DISCOUNT / 100)
            logger.info("Применена скидка для стартапа/НКО: %d%% (-%d₽)", STARTUP_NGO_DISCOUNT, startup_discount_amount)
        
        # 6. Итоговые суммы
        total_discount_amount = package_discount_amount + annual_discount_amount + startup_discount_amount
        total_annual = products_subtotal - total_discount_amount
        total_monthly = int(total_annual / 12)  # Среднемесячный платёж
        total_with_services = total_annual + services_subtotal
        
        result = PricingResult(
            products=products,
            services=services,
            products_subtotal=products_subtotal,
            services_subtotal=services_subtotal,
            package_discount_name=package_discount_name,
            package_discount_percent=package_discount_percent,
            package_discount_amount=package_discount_amount,
            annual_discount_applied=annual_discount_applied,
            annual_discount_amount=annual_discount_amount,
            startup_discount_applied=startup_discount_applied,
            startup_discount_amount=startup_discount_amount,
            total_discount_amount=total_discount_amount,
            total_monthly=total_monthly,
            total_annual=total_annual,
            total_with_services=total_with_services,
        )
        
        logger.info(
            "Расчёт завершён: итого %d₽/год (скидка %d₽)",
            result.total_annual,
            result.total_discount_amount
        )
        
        return result
    
    def _find_package_discount(
        self,
        selected_products: set[ProductType]
    ) -> PackageDiscount | None:
        """Ищет подходящую пакетную скидку."""
        # Ищем от большего к меньшему (больше продуктов = больше скидка)
        for package in sorted(self.packages, key=lambda p: len(p.products), reverse=True):
            if set(package.products) == selected_products:
                return package
        return None


# Singleton
pricing_calculator = PricingCalculator()
```

3. tests/unit/test_pricing_calculator.py (НОВЫЙ)
   Unit-тесты калькулятора:
```python
"""Unit-тесты калькулятора стоимости."""

import pytest

from app.core.pricing_rules import ProductType, ServiceType
from app.services.pricing.calculator import (
    pricing_calculator,
    SelectedProduct,
    SelectedService,
)


def test_find_tariff_ai_manager():
    """Тест поиска тарифа AI-Manager."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    
    assert tariff is not None
    assert tariff.name == "Бизнес"
    assert tariff.price_monthly == 150_000
    assert tariff.users_limit == 20


def test_find_tariff_by_users():
    """Тест подбора тарифа по количеству пользователей."""
    # 3 пользователя -> Старт
    tariff = pricing_calculator.find_tariff_by_users(ProductType.AI_MANAGER, 3)
    assert tariff.name == "Старт"
    assert tariff.price_monthly == 80_000
    
    # 15 пользователей -> Бизнес
    tariff = pricing_calculator.find_tariff_by_users(ProductType.AI_MANAGER, 15)
    assert tariff.name == "Бизнес"
    
    # 80 пользователей -> Корпорация
    tariff = pricing_calculator.find_tariff_by_users(ProductType.AI_MANAGER, 80)
    assert tariff.name == "Корпорация"


def test_single_product_no_discounts():
    """Тест расчёта для одного продукта без скидок."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_MANAGER, tariff, months=12)],
        services=[],
        apply_annual_discount=False,
        apply_startup_discount=False
    )
    
    # Без скидок
    assert result.products_subtotal == 150_000 * 12  # 1,800,000
    assert result.total_discount_amount == 0
    assert result.total_annual == 1_800_000
    assert result.total_monthly == 150_000


def test_package_discount_digital_office():
    """Тест пакетной скидки 'Цифровой офис' (15%)."""
    manager_tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    lawyer_tariff = pricing_calculator.find_tariff(ProductType.AI_LAWYER, "Команда")
    
    result = pricing_calculator.calculate(
        products=[
            SelectedProduct(ProductType.AI_MANAGER, manager_tariff, months=12),
            SelectedProduct(ProductType.AI_LAWYER, lawyer_tariff, months=12),
        ]
    )
    
    # Базовая стоимость: (150,000 + 100,000) × 12 = 3,000,000
    assert result.products_subtotal == 3_000_000
    
    # Скидка 15%
    assert result.package_discount_name == "Цифровой офис"
    assert result.package_discount_percent == 15
    assert result.package_discount_amount == 450_000
    
    # Итого
    assert result.total_annual == 2_550_000


def test_package_discount_full_automation():
    """Тест пакета 'Полная автоматизация' (20%)."""
    manager = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    lawyer = pricing_calculator.find_tariff(ProductType.AI_LAWYER, "Команда")
    analyst = pricing_calculator.find_tariff(ProductType.AI_ANALYST, "Стандарт")
    
    result = pricing_calculator.calculate(
        products=[
            SelectedProduct(ProductType.AI_MANAGER, manager, months=12),
            SelectedProduct(ProductType.AI_LAWYER, lawyer, months=12),
            SelectedProduct(ProductType.AI_ANALYST, analyst, months=12),
        ]
    )
    
    # Базовая стоимость: (150,000 + 100,000 + 120,000) × 12 = 4,440,000
    assert result.products_subtotal == 4_440_000
    
    # Скидка 20%
    assert result.package_discount_name == "Полная автоматизация"
    assert result.package_discount_percent == 20
    assert result.package_discount_amount == 888_000
    
    # Итого
    assert result.total_annual == 3_552_000


def test_annual_payment_discount():
    """Тест скидки за годовую оплату (15%)."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_MANAGER, tariff, months=12)],
        apply_annual_discount=True
    )
    
    # Базовая стоимость: 150,000 × 12 = 1,800,000
    assert result.products_subtotal == 1_800_000
    
    # Скидка 15%
    assert result.annual_discount_applied is True
    assert result.annual_discount_amount == 270_000
    
    # Итого
    assert result.total_annual == 1_530_000


def test_startup_discount():
    """Тест скидки для стартапов (20%)."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_ANALYST, "Лайт")
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_ANALYST, tariff, months=12)],
        apply_startup_discount=True
    )
    
    # Базовая стоимость: 60,000 × 12 = 720,000
    assert result.products_subtotal == 720_000
    
    # Скидка 20%
    assert result.startup_discount_applied is True
    assert result.startup_discount_amount == 144_000
    
    # Итого
    assert result.total_annual == 576_000


def test_combined_discounts():
    """Тест комбинации скидок (пакет + годовая + стартап)."""
    manager = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Старт")
    analyst = pricing_calculator.find_tariff(ProductType.AI_ANALYST, "Лайт")
    
    result = pricing_calculator.calculate(
        products=[
            SelectedProduct(ProductType.AI_MANAGER, manager, months=12),
            SelectedProduct(ProductType.AI_ANALYST, analyst, months=12),
        ],
        apply_annual_discount=True,
        apply_startup_discount=True
    )
    
    # Базовая стоимость: (80,000 + 60,000) × 12 = 1,680,000
    assert result.products_subtotal == 1_680_000
    
    # Пакетная скидка 15%: 252,000
    assert result.package_discount_amount == 252_000
    
    # После пакетной: 1,428,000
    # Годовая скидка 15%: 214,200
    assert result.annual_discount_amount == 214_200
    
    # После годовой: 1,213,800
    # Стартап скидка 20%: 242,760
    assert result.startup_discount_amount == 242_760
    
    # Итого
    assert result.total_annual == 971_040
    assert result.total_discount_amount == 708_960


def test_additional_services():
    """Тест расчёта с дополнительными услугами."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
    
    implementation = pricing_calculator.get_service(ServiceType.IMPLEMENTATION)
    training = pricing_calculator.get_service(ServiceType.TRAINING)
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_MANAGER, tariff, months=12)],
        services=[
            SelectedService(implementation, quantity=1),
            SelectedService(training, quantity=3),  # 3 дня обучения
        ]
    )
    
    # Продукты: 1,800,000
    assert result.products_subtotal == 1_800_000
    
    # Услуги: 80,000 + (15,000 × 3) = 125,000
    assert result.services_subtotal == 125_000
    
    # Итого с услугами
    assert result.total_with_services == 1_925_000


def test_format_summary():
    """Тест форматирования сводки."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_LAWYER, "Соло")
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_LAWYER, tariff, months=12)],
        apply_annual_discount=True
    )
    
    summary = result.format_summary()
    
    assert "💰 РАСЧЁТ СТОИМОСТИ" in summary
    assert "ai_lawyer" in summary
    assert "600,000₽" in summary  # Базовая стоимость
    assert "Годовая оплата" in summary
    assert "510,000₽" in summary  # После скидки 15%


def test_enterprise_tariff_warning(caplog):
    """Тест предупреждения об энтерпрайз тарифе."""
    tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Энтерпрайз")
    
    result = pricing_calculator.calculate(
        products=[SelectedProduct(ProductType.AI_MANAGER, tariff, months=12)]
    )
    
    # Энтерпрайз тариф имеет price = 0, не учитывается в расчёте
    assert result.products_subtotal == 0
    assert "энтерпрайз тариф" in caplog.text.lower()
```

ТРЕБОВАНИЯ:
- Все тарифы из pricing.md
- Пакетные скидки (15-20%)
- Годовая скидка (15%)
- Скидка для стартапов/НКО (20%)
- Каскадное применение скидок (пакет → годовая → стартап)
- Расчёт дополнительных услуг
- Подбор тарифа по количеству пользователей
- Форматирование сводки для документов
- Обработка энтерпрайз тарифов (индивидуально)

ИСПОЛЬЗОВАНИЕ:
```python
from app.services.pricing.calculator import pricing_calculator, SelectedProduct, SelectedService
from app.core.pricing_rules import ProductType, ServiceType

# Подбор тарифа
tariff = pricing_calculator.find_tariff(ProductType.AI_MANAGER, "Бизнес")
# или
tariff = pricing_calculator.find_tariff_by_users(ProductType.AI_MANAGER, users_count=15)

# Расчёт
result = pricing_calculator.calculate(
    products=[
        SelectedProduct(ProductType.AI_MANAGER, tariff, months=12)
    ],
    services=[
        SelectedService(
            pricing_calculator.get_service(ServiceType.IMPLEMENTATION),
            quantity=1
        )
    ],
    apply_annual_discount=True,
    apply_startup_discount=False
)

# Вывод
print(result.format_summary())
print(f"Итого в год: {result.total_annual:,}₽")
```

ИНТЕГРАЦИЯ С ГЕНЕРАЦИЕЙ ДОКУМЕНТОВ:
В app/services/documents/generator.py использовать PricingResult для автозаполнения КП

ЛОГИРОВАНИЕ:
- INFO: начало расчёта, применение скидок, итоги
- WARNING: энтерпрайз тарифы (требуют индивидуального расчёта)
- DEBUG: промежуточные вычисления

⚠️ КРИТИЧНО:
- Все цены в рублях (int)
- Скидки применяются каскадом
- Энтерпрайз тарифы имеют price=0 и флаг is_enterprise
- Unit-тесты должны покрывать ≥90%
- Типизация везде (type hints)
- Dataclasses для структур данных

ПРОВЕРКА:
```bash
# Запуск тестов
pytest tests/unit/test_pricing_calculator.py -v

# Проверка покрытия
pytest tests/unit/test_pricing_calculator.py --cov=app.services.pricing --cov-report=html
```


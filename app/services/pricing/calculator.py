"""Сервис расчёта стоимости AI-решений."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from loguru import logger

from app.core.pricing_rules import (
    ADDITIONAL_SERVICES,
    PACKAGE_DISCOUNTS,
    ANNUAL_PAYMENT_DISCOUNT,
    STARTUP_NGO_DISCOUNT,
    AdditionalService,
    PackageDiscount,
    ProductType,
    ServiceType,
    TariffPlan,
    get_all_tariffs,
)


@dataclass(frozen=True)
class SelectedProduct:
    """Выбранный продукт с тарифом."""

    product: ProductType
    tariff: TariffPlan
    months: int = 12


@dataclass(frozen=True)
class SelectedService:
    """Выбранная дополнительная услуга."""

    service: AdditionalService
    quantity: int = 1


@dataclass(frozen=True)
class PricingResult:
    """Результат расчёта стоимости."""

    products: list[SelectedProduct]
    services: list[SelectedService]
    products_subtotal: int
    services_subtotal: int
    package_discount_name: str | None
    package_discount_percent: int
    package_discount_amount: int
    annual_discount_applied: bool
    annual_discount_amount: int
    startup_discount_applied: bool
    startup_discount_amount: int
    total_discount_amount: int
    total_monthly: int
    total_annual: int
    total_with_services: int

    def format_summary(self) -> str:
        """Форматирует краткую сводку."""
        lines: list[str] = ["💰 РАСЧЁТ СТОИМОСТИ", ""]

        lines.append("📦 Продукты:")
        for product in self.products:
            tariff_price = f"{product.tariff.price_monthly:,}".replace(",", " ")
            lines.append(
                f"  • {product.product.value} ({product.tariff.name}): "
                f"{tariff_price}₽/мес × {product.months} мес",
            )
        products_total = f"{self.products_subtotal:,}".replace(",", " ")
        lines.append(f"Итого за продукты: {products_total}₽")
        lines.append("")

        if self.services:
            lines.append("🛠 Дополнительные услуги:")
            for service in self.services:
                service_price = f"{service.service.price:,}".replace(",", " ")
                lines.append(
                    f"  • {service.service.name}: {service_price}₽ × {service.quantity}",
                )
            services_total = f"{self.services_subtotal:,}".replace(",", " ")
            lines.append(f"Итого за услуги: {services_total}₽")
            lines.append("")

        if self.total_discount_amount > 0:
            lines.append("🎁 Скидки:")
            if self.package_discount_amount > 0 and self.package_discount_name:
                discount = f"{self.package_discount_amount:,}".replace(",", " ")
                lines.append(
                    f"  • Пакет '{self.package_discount_name}': "
                    f"-{self.package_discount_percent}% ({discount}₽)",
                )
            if self.annual_discount_amount > 0:
                discount = f"{self.annual_discount_amount:,}".replace(",", " ")
                lines.append(
                    f"  • Годовая оплата: -{ANNUAL_PAYMENT_DISCOUNT}% ({discount}₽)",
                )
            if self.startup_discount_amount > 0:
                discount = f"{self.startup_discount_amount:,}".replace(",", " ")
                lines.append(
                    f"  • Стартап/НКО: -{STARTUP_NGO_DISCOUNT}% ({discount}₽)",
                )
            total_discount = f"{self.total_discount_amount:,}".replace(",", " ")
            lines.append(f"Всего скидка: {total_discount}₽")
            lines.append("")

        monthly_total = f"{self.total_monthly:,}".replace(",", " ")
        annual_total = f"{self.total_annual:,}".replace(",", " ")
        lines.append("💵 ИТОГО:")
        lines.append(f"Ежемесячно: {monthly_total}₽")
        lines.append(f"За год: {annual_total}₽")
        if self.services:
            services_total = f"{self.total_with_services:,}".replace(",", " ")
            lines.append(f"С услугами: {services_total}₽")

        return "\n".join(lines)


class PricingCalculator:
    """Калькулятор стоимости AI-решений."""

    def __init__(self) -> None:
        self._all_tariffs = get_all_tariffs()
        self._services = {
            service.service_type: service for service in ADDITIONAL_SERVICES
        }
        self._packages = PACKAGE_DISCOUNTS

    def find_tariff(self, product: ProductType, tariff_name: str) -> TariffPlan | None:
        """Находит тариф по названию."""
        tariffs = self._all_tariffs.get(product, [])
        for tariff in tariffs:
            if tariff.name.lower() == tariff_name.lower():
                return tariff
        return None

    def find_tariff_by_users(
        self, product: ProductType, users_count: int
    ) -> TariffPlan | None:
        """Подбирает тариф по количеству пользователей."""
        tariffs = sorted(
            self._all_tariffs.get(product, []),
            key=lambda item: item.price_monthly,
        )

        for tariff in tariffs:
            if tariff.is_enterprise:
                continue
            if tariff.users_limit is None or users_count <= tariff.users_limit:
                return tariff

        for tariff in tariffs:
            if tariff.is_enterprise:
                return tariff

        return None

    def get_service(self, service_type: ServiceType) -> AdditionalService | None:
        """Возвращает услугу по её типу."""
        return self._services.get(service_type)

    def calculate(
        self,
        products: Iterable[SelectedProduct],
        services: Iterable[SelectedService] | None = None,
        apply_annual_discount: bool = False,
        apply_startup_discount: bool = False,
    ) -> PricingResult:
        """Рассчитывает стоимость выбранных продуктов и услуг."""
        product_list = list(products)
        service_list = list(services or [])

        logger.info(
            "Расчёт стоимости: продуктов=%d, услуг=%d",
            len(product_list),
            len(service_list),
        )

        enterprise_selected = any(
            product.tariff.is_enterprise for product in product_list
        )
        if enterprise_selected:
            logger.warning(
                "Обнаружен энтерпрайз тариф — требуется индивидуальный расчёт"
            )

        products_subtotal = sum(
            product.tariff.price_monthly * product.months
            for product in product_list
            if not product.tariff.is_enterprise
        )

        services_subtotal = sum(
            service.service.price * service.quantity for service in service_list
        )

        selected_products = {product.product for product in product_list}
        package_discount = self._find_package_discount(selected_products)

        package_discount_name: str | None = None
        package_discount_percent = 0
        package_discount_amount = 0

        if package_discount:
            package_discount_name = package_discount.name
            package_discount_percent = package_discount.discount_percent
            package_discount_amount = int(
                products_subtotal * package_discount_percent / 100
            )
            logger.info(
                "Применена пакетная скидка '%s': %d%% (-%d₽)",
                package_discount_name,
                package_discount_percent,
                package_discount_amount,
            )

        annual_discount_amount = 0
        if apply_annual_discount:
            base = products_subtotal - package_discount_amount
            annual_discount_amount = int(base * ANNUAL_PAYMENT_DISCOUNT / 100)
            logger.info(
                "Применена скидка за годовую оплату: %d%% (-%d₽)",
                ANNUAL_PAYMENT_DISCOUNT,
                annual_discount_amount,
            )

        startup_discount_amount = 0
        if apply_startup_discount:
            base = products_subtotal - package_discount_amount - annual_discount_amount
            startup_discount_amount = int(base * STARTUP_NGO_DISCOUNT / 100)
            logger.info(
                "Применена скидка для стартапа/НКО: %d%% (-%d₽)",
                STARTUP_NGO_DISCOUNT,
                startup_discount_amount,
            )

        total_discount_amount = (
            package_discount_amount + annual_discount_amount + startup_discount_amount
        )
        total_annual = products_subtotal - total_discount_amount
        total_monthly = total_annual // 12
        total_with_services = total_annual + services_subtotal

        result = PricingResult(
            products=product_list,
            services=service_list,
            products_subtotal=products_subtotal,
            services_subtotal=services_subtotal,
            package_discount_name=package_discount_name,
            package_discount_percent=package_discount_percent,
            package_discount_amount=package_discount_amount,
            annual_discount_applied=apply_annual_discount,
            annual_discount_amount=annual_discount_amount,
            startup_discount_applied=apply_startup_discount,
            startup_discount_amount=startup_discount_amount,
            total_discount_amount=total_discount_amount,
            total_monthly=total_monthly,
            total_annual=total_annual,
            total_with_services=total_with_services,
        )

        logger.info(
            "Расчёт завершён: итого %d₽/год (скидка %d₽)",
            result.total_annual,
            result.total_discount_amount,
        )

        return result

    def _find_package_discount(
        self, selected_products: set[ProductType]
    ) -> PackageDiscount | None:
        """Ищет подходящую пакетную скидку."""
        sorted_packages = sorted(
            self._packages,
            key=lambda package: len(package.products),
            reverse=True,
        )
        for package in sorted_packages:
            if set(package.products) == selected_products:
                return package
        return None


pricing_calculator = PricingCalculator()

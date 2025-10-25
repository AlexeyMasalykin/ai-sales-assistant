"""API endpoints для amoCRM OAuth и управления."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.core.dependencies import get_current_user, get_service_name
from app.integrations.amocrm.auth import auth_manager
from app.integrations.amocrm.models import LeadCreateRequest
from app.services.crm.amocrm_service import amocrm_service


router = APIRouter(prefix="/amocrm", tags=["amoCRM"])


@router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str | None = Query(None),
):
    """
    OAuth callback endpoint для amoCRM.

    После авторизации amoCRM перенаправляет сюда с code.
    """
    logger.info("amoCRM OAuth callback: code=%s...", code[:20])

    try:
        tokens = await auth_manager.exchange_code_for_tokens(code)

        return {
            "success": True,
            "message": "Авторизация успешна! Токены сохранены.",
            "expires_in": tokens.expires_in,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка OAuth авторизации: %s", str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/leads")
async def create_lead_endpoint(
    request: LeadCreateRequest,
    current_user = Depends(get_current_user),  # type: ignore[assignment]
):
    """
    Создаёт лид в amoCRM из данных диалога.

    Требует JWT авторизацию (пользовательский или сервисный токен).
    Используется ботами (Telegram, Avito) для автоматического создания лидов.
    """
    try:
        if hasattr(current_user, "model_dump"):
            payload_dict = current_user.model_dump()
        elif isinstance(current_user, dict):
            payload_dict = current_user
        else:
            payload_dict = {"id": getattr(current_user, "sub", None)}

        service_name = get_service_name(current_user)
        creator_id = service_name or payload_dict.get("id") or payload_dict.get("sub")

        logger.info(
            f"API запрос на создание лида от: {service_name or f'user_{creator_id}'}"
        )

        result = await amocrm_service.create_lead_from_conversation(
            request,
            user_id=creator_id,
        )

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"400: {result.message}",
            )

        return {
            "lead_id": result.lead_id,
            "contact_id": result.contact_id,
            "success": True,
            "message": result.message,
        }

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Ошибка создания лида: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутренняя ошибка при создании лида: {str(exc)}",
        )


@router.get("/auth/url")
async def get_auth_url():
    """Возвращает URL для первичной OAuth авторизации."""
    from app.core.config import get_settings

    settings = get_settings()

    auth_url = (
        f"https://{settings.amocrm_subdomain}.amocrm.ru/oauth?"
        f"client_id={settings.amocrm_client_id}&"
        f"redirect_uri={settings.amocrm_redirect_uri}&"
        f"response_type=code&"
        f"state=random_state"
    )

    return {
        "auth_url": auth_url,
        "instructions": "Перейдите по ссылке для авторизации",
    }

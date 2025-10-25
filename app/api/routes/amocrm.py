"""API endpoints для amoCRM OAuth и управления."""
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from app.core.dependencies import get_current_user
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
    current_user: dict = Depends(get_current_user),
):
    """
    Создаёт лид в amoCRM из данных диалога.

    Требует JWT авторизацию.
    Используется ботами (Telegram, Avito) для автоматического создания лидов.
    """
    if isinstance(current_user, dict):
        current_payload: dict | None = current_user
    else:
        try:
            current_payload = current_user.model_dump()
        except AttributeError:
            current_payload = None

    if current_payload and "id" not in current_payload and current_payload.get("sub"):
        current_payload["id"] = current_payload["sub"]

    try:
        result = await amocrm_service.create_lead_from_conversation(
            request,
            user_id=current_payload.get("id") if current_payload else None,
        )

        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return result

    except Exception as exc:  # noqa: BLE001
        logger.error("Ошибка создания лида: %s", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


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

"""API endpoints для amoCRM OAuth и управления."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from app.core.dependencies import get_current_user, get_service_name
from app.integrations.amocrm.auth import auth_manager
from app.integrations.amocrm.models import LeadCreateRequest
from app.services.crm.amocrm_service import amocrm_service


router = APIRouter(prefix="/amocrm", tags=["amoCRM"])


@router.get("/callback")
async def oauth_callback(
    code: str | None = Query(None, description="Authorization code"),
    state: str | None = Query(None),
):
    """
    OAuth callback endpoint для amoCRM.

    После авторизации amoCRM перенаправляет сюда с code.
    """
    # Если зашли без code - показываем информационную страницу
    if not code:
        logger.info("⚠️ Callback вызван без параметра code")
        return HTMLResponse(
            content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>amoCRM OAuth Callback</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }
                        .container {
                            background: white;
                            padding: 40px;
                            border-radius: 10px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 600px;
                        }
                        h1 { color: #667eea; margin-bottom: 20px; }
                        p { color: #666; font-size: 16px; line-height: 1.6; }
                        .info-icon {
                            font-size: 64px;
                            margin-bottom: 20px;
                        }
                        code {
                            background: #f4f4f4;
                            padding: 2px 6px;
                            border-radius: 3px;
                            font-family: monospace;
                        }
                        .link {
                            margin-top: 20px;
                            padding: 15px;
                            background: #f0f0f0;
                            border-radius: 5px;
                        }
                        a {
                            color: #667eea;
                            text-decoration: none;
                            font-weight: bold;
                        }
                        a:hover {
                            text-decoration: underline;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="info-icon">ℹ️</div>
                        <h1>amoCRM OAuth Callback Endpoint</h1>
                        <p>Это служебный endpoint для OAuth авторизации amoCRM.</p>
                        <p>После успешной авторизации в amoCRM вы будете автоматически перенаправлены сюда с authorization code.</p>
                        <div class="link">
                            <p><strong>Для авторизации перейдите по ссылке:</strong></p>
                            <a href="/api/v1/amocrm/auth/url" target="_blank">Получить OAuth URL</a>
                        </div>
                        <p style="margin-top: 30px; font-size: 14px; color: #999;">
                            Sales Assistant • amoCRM Integration
                        </p>
                    </div>
                </body>
                </html>
            """
        )

    logger.info("=" * 50)
    logger.info("🔑 amoCRM OAuth callback вызван!")
    logger.info("Code (первые 20 символов): %s...", code[:20])
    logger.info("State: %s", state)
    logger.info("=" * 50)

    try:
        # Обмениваем code на токены
        logger.info("Начинаем обмен code на токены...")
        tokens = await auth_manager.exchange_code_for_tokens(code)

        if not tokens:
            logger.error("❌ Не удалось получить токены от amoCRM")
            return HTMLResponse(
                status_code=500,
                content="""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>Ошибка авторизации</title>
                        <style>
                            body {
                                font-family: Arial, sans-serif;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                height: 100vh;
                                margin: 0;
                                background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
                            }
                            .container {
                                background: white;
                                padding: 40px;
                                border-radius: 10px;
                                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                                text-align: center;
                            }
                            h1 { color: #f5576c; margin-bottom: 20px; }
                            p { color: #666; font-size: 18px; }
                            .error-icon {
                                font-size: 64px;
                                margin-bottom: 20px;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="error-icon">❌</div>
                            <h1>Ошибка авторизации</h1>
                            <p>Не удалось получить токены от amoCRM.</p>
                            <p>Проверьте настройки OAuth и повторите попытку.</p>
                        </div>
                    </body>
                    </html>
                """,
            )

        logger.info("✅ Токены успешно получены!")
        logger.info(
            "Access token (первые 20 символов): %s...",
            tokens.access_token[:20],
        )
        logger.info("Refresh token получен: %s", bool(tokens.refresh_token))
        logger.info("Expires in: %s секунд", tokens.expires_in)

        # Возвращаем HTML с успехом
        return HTMLResponse(
            content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Авторизация успешна</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }
                        .container {
                            background: white;
                            padding: 40px;
                            border-radius: 10px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }
                        h1 { color: #4CAF50; margin-bottom: 20px; }
                        p { color: #666; font-size: 18px; margin: 10px 0; }
                        .success-icon {
                            font-size: 64px;
                            margin-bottom: 20px;
                        }
                        .info {
                            background: #f0f0f0;
                            padding: 15px;
                            border-radius: 5px;
                            margin-top: 20px;
                            font-size: 14px;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success-icon">✅</div>
                        <h1>Авторизация успешна!</h1>
                        <p><strong>amoCRM</strong> успешно подключён к Sales Assistant.</p>
                        <p>Токены сохранены и готовы к использованию.</p>
                        <div class="info">
                            <p><strong>Что дальше?</strong></p>
                            <p>Бот теперь может создавать лиды и синхронизировать данные с amoCRM.</p>
                        </div>
                        <p style="margin-top: 30px; font-size: 14px; color: #999;">
                            Можете закрыть это окно.
                        </p>
                    </div>
                </body>
                </html>
            """
        )

    except Exception as exc:  # noqa: BLE001
        logger.error("❌ Ошибка в OAuth callback: %s", str(exc))
        logger.exception(exc)

        return HTMLResponse(
            status_code=500,
            content=f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Ошибка авторизации</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #f5576c 0%, #f093fb 100%);
                        }}
                        .container {{
                            background: white;
                            padding: 40px;
                            border-radius: 10px;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 600px;
                        }}
                        h1 {{ color: #f5576c; margin-bottom: 20px; }}
                        p {{ color: #666; font-size: 16px; margin: 10px 0; }}
                        .error-icon {{
                            font-size: 64px;
                            margin-bottom: 20px;
                        }}
                        .error-details {{
                            background: #fff3cd;
                            border: 1px solid #ffc107;
                            padding: 15px;
                            border-radius: 5px;
                            margin-top: 20px;
                            text-align: left;
                            font-family: monospace;
                            font-size: 12px;
                            word-break: break-all;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error-icon">❌</div>
                        <h1>Ошибка авторизации</h1>
                        <p>Произошла ошибка при обработке OAuth callback.</p>
                        <div class="error-details">
                            <strong>Детали ошибки:</strong><br>
                            {str(exc)}
                        </div>
                        <p style="margin-top: 20px; font-size: 14px;">
                            Проверьте логи приложения для подробной информации.
                        </p>
                    </div>
                </body>
                </html>
            """,
        )


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

    logger.info("=" * 50)
    logger.info("Формирование OAuth URL")
    logger.info("amocrm_subdomain: %s", settings.amocrm_subdomain)
    logger.info("amocrm_client_id: %s", settings.amocrm_client_id)
    logger.info("amocrm_redirect_uri: %s", settings.amocrm_redirect_uri)
    logger.info("=" * 50)

    # Правильный формат OAuth URL для amoCRM
    # Используем mode=post_message для корректной работы
    auth_url = (
        f"https://www.amocrm.ru/oauth?"
        f"client_id={settings.amocrm_client_id}&"
        f"state=random_state&"
        f"mode=post_message"
    )

    logger.info("Сформированный auth_url: %s", auth_url)

    return {
        "auth_url": auth_url,
        "instructions": "Перейдите по ссылке для авторизации",
    }

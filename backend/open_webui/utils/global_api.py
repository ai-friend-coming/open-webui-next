from contextlib import contextmanager
from typing import Optional, Dict, Any
from fastapi import Request
import logging

log = logging.getLogger(__name__)


def get_global_api_config(request: Request) -> Optional[Dict[str, Any]]:
    """
    Return the Global API configuration if complete; otherwise return None.
    """
    global_api_key = getattr(request.app.state.config, "GLOBAL_API_KEY", None)
    global_api_base_url = getattr(request.app.state.config, "GLOBAL_API_BASE_URL", None)
    global_api_model_id = getattr(request.app.state.config, "GLOBAL_API_MODEL_ID", None)
    global_api_input_price = getattr(
        request.app.state.config, "GLOBAL_API_INPUT_PRICE", None
    )
    global_api_output_price = getattr(
        request.app.state.config, "GLOBAL_API_OUTPUT_PRICE", None
    )

    if global_api_key:
        global_api_key = getattr(global_api_key, "value", global_api_key)
    if global_api_base_url:
        global_api_base_url = getattr(
            global_api_base_url, "value", global_api_base_url
        )
    if global_api_model_id:
        global_api_model_id = getattr(global_api_model_id, "value", global_api_model_id)
    if global_api_input_price:
        global_api_input_price = getattr(
            global_api_input_price, "value", global_api_input_price
        )
    if global_api_output_price:
        global_api_output_price = getattr(
            global_api_output_price, "value", global_api_output_price
        )

    if (
        global_api_key
        and isinstance(global_api_key, str)
        and global_api_key.strip()
        and global_api_base_url
        and isinstance(global_api_base_url, str)
        and global_api_base_url.strip()
        and global_api_model_id
        and isinstance(global_api_model_id, str)
        and global_api_model_id.strip()
    ):
        return {
            "key": global_api_key,
            "base_url": global_api_base_url,
            "model_id": global_api_model_id,
            "input_price": int(global_api_input_price) if global_api_input_price else 0,
            "output_price": int(global_api_output_price) if global_api_output_price else 0,
        }
    return None


@contextmanager
def temporary_request_state(
    request: Request,
    is_user_model: bool,
    model_config: Optional[Dict[str, Any]],
    model_id: Optional[str],
    purpose: str = "摘要生成",
):
    """
    Temporarily set request.state for model selection.

    Priority:
    1) user model (no billing) if is_user_model=True
    2) global API if configured (billing)
    3) platform model (billing)
    """
    local_request = request
    original_direct = getattr(local_request.state, "direct", None)
    original_model = getattr(local_request.state, "model", None)

    global_api_config = None
    use_direct = False

    if is_user_model:
        effective_model_config = model_config
        use_direct = True
        log.info(f"{purpose}使用用户私有模型（不扣费）: model={model_id}")
    else:
        global_api_config = get_global_api_config(request)
        if global_api_config:
            effective_model_config = {
                "id": global_api_config["model_id"],
                "base_url": global_api_config["base_url"],
                "api_key": global_api_config["key"],
            }
            use_direct = True
            log.info(
                f"{purpose}使用 Global API（扣费）: "
                f"model={global_api_config['model_id']}, base_url={global_api_config['base_url']}"
            )
        else:
            effective_model_config = model_config
            log.info(f"{purpose}使用平台模型（扣费）: model={model_id}")

    if use_direct:
        local_request.state.direct = True
        local_request.state.model = effective_model_config
        if effective_model_config:
            log.debug(
                "设置 request.state: direct=True, model_id=%s, base_url=%s",
                effective_model_config.get("id", "unknown"),
                effective_model_config.get("base_url"),
            )
    else:
        log.debug("设置 request.state: 使用平台模型 %s", model_id)

    try:
        yield local_request
    finally:
        if original_direct is None:
            if hasattr(local_request.state, "direct"):
                delattr(local_request.state, "direct")
        else:
            local_request.state.direct = original_direct

        if original_model is None:
            if hasattr(local_request.state, "model"):
                delattr(local_request.state, "model")
        else:
            local_request.state.model = original_model

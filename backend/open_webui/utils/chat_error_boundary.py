import asyncio
import logging
import time
import traceback
from contextlib import asynccontextmanager

from open_webui.models.chats import Chats
from open_webui.socket.main import get_event_emitter

log = logging.getLogger(__name__)

class CustmizedError(Exception):
    def __init__(self, user_toast_message: str, cause: Exception | None = None):
        super().__init__(user_toast_message)
        self.user_toast_message = user_toast_message
        self.cause = cause
        if cause:
            self.debug_log = "".join(
                traceback.format_exception(type(cause), cause, cause.__traceback__)
            )
        else:
            self.debug_log = traceback.format_exc()

    def __str__(self) -> str:
        return str(self.user_toast_message or super().__str__())

@asynccontextmanager
async def chat_error_boundary(metadata, user):
    try:
        yield
    except asyncio.CancelledError:
        log.info("Chat processing was cancelled")
        event_emitter = get_event_emitter(metadata)
        await event_emitter(
            {"type": "chat:tasks:cancel"},  # 通知前端任务已取消
        )
    except Exception as e:

        if isinstance(e, CustmizedError):
            log.exception(
                f"Error processing chat payload: {e.user_toast_message}",
                exc_info=e.cause or e,
            )
            user_toast_message = e.user_toast_message
            debug_log = e.debug_log
        else:
            log.exception(f"Error processing chat payload: {e}")
            user_toast_message = "出现了错误，请联系管理员！"
            debug_log = traceback.format_exc()
        
        if metadata.get("chat_id") and metadata.get("message_id"):

            # 使用 chat.meta["error_messages"] 存储错误记录
            Chats.add_error_message_by_user_id_and_chat_id(
                user.id,
                metadata["chat_id"],
                {
                    "error": {
                        "user_toast_message": user_toast_message,
                        "debug_log": debug_log,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                    }
                },
            )

            # 通过 WebSocket 发送错误事件到前端（临时通知）
            event_emitter = get_event_emitter(metadata)
            
            await event_emitter(
                {
                    "type": "chat:message:error",
                    "data": {"error": {"content": user_toast_message}},
                }
            )
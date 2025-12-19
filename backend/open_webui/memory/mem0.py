
from mem0 import MemoryClient
import os
from logging import getLogger
from typing import List, Dict, Optional

from fastapi import HTTPException

from open_webui.billing.core import deduct_balance

log = getLogger(__name__)

mem0_api_key = os.getenv("MEM0_API_KEY")
memory_client = MemoryClient(api_key=mem0_api_key)

# 计费常量
BILLING_UNIT_TOKENS = 1
MEM0_SEARCH_MODEL_ID = "RAG"
MEM0_ADD_MODEL_ID = "RAG"


def _charge_mem0(user_id: str, model_id: str):
    """
    为 mem0 操作扣费。利用固定 token 单位和 ratio.py 中的定价得到固定费用。
    """
    deduct_balance(
        user_id=user_id,
        model_id=model_id,
        prompt_tokens=BILLING_UNIT_TOKENS,
        completion_tokens=0,
        log_type="RAG",
    )

async def mem0_search(user_id: str, chat_id: str, last_message: str) -> list[str]:
    """
    未来可替换为实际检索逻辑，返回若干相关记忆条目（字符串）。
    增加 chat_id 便于按会话窗口区分/隔离记忆。
    """
    try:
        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID)
        # TODO: 接入真实 Mem0 检索
        log.info(f"mem0_search called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
        serach_rst = memory_client.search(
        query=last_message, 
       filters={"user_id": user_id}
    )
        memories=serach_rst["results"] if "results" in serach_rst else serach_rst
        log.info(f"mem0_search found {len(memories)} memories")
        return [mem["text"] for mem in memories]
    except Exception as e:
        log.debug(f"Mem0 search failed: {e}")
        return []

async def mem0_search_and_add(user_id: str, chat_id: str, last_message: str) -> list[Dict]:
    """
    检索并添加记忆，添加记忆使用mem0 的add功能，返回若干相关记忆条目（字符串）。
    增加 chat_id 便于按会话窗口区分/隔离记忆。
    """
    try:
        # 先对检索计费
        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID)
        # TODO: 接入真实 Mem0 检索
        log.info(f"mem0_search called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
        serach_rst = memory_client.search(
        query=last_message, 
       filters={"user_id": user_id}
    )
        if "results" not in serach_rst:
            log.info("mem0_search_and_add no results found, skipping add")
            memories=[]
        else:
            log.info(f"mem0_search_and_add found {len(serach_rst['results'])} results")
            memories=serach_rst["results"]
        added_messages= [{"role": "user", "content": last_message}]
        memory_client.add(added_messages, user_id=user_id,enable_graph=True,async_mode=True, metadata={"session_id": chat_id})
        # 再对添加计费
        # _charge_mem0(user_id, MEM0_ADD_MODEL_ID)
        log.info(f"mem0_add added message for user_id: {user_id}")
        return memories
    except Exception as e:
        log.debug(f"Mem0 search and add failed: {e}")
        return []
        
async def mem0_delete(user_id: str, chat_id: str) -> bool:
    """
    删除指定用户在指定 chat 窗口下的所有 Mem0 相关记忆（占位实现）。
    未来可替换为实际删除逻辑。
    """
    try:
        # TODO: 接入真实删除逻辑（如按 chat_id 过滤）
        log.info(f"mem0_delete called with user_id: {user_id}, chat_id: {chat_id}")
        memory_client.delete(
            filters={"user_id": user_id}
        )
        return True
    except Exception as e:
        log.debug(f"Mem0 delete failed: {e}")
        return False

import os
import zlib
import re  # [新增] 用于正则匹配
from logging import getLogger
from typing import Dict, List

from mem0 import MemoryClient
from open_webui.billing.core import deduct_balance

log = getLogger(__name__)

mem0_api_key = os.getenv("MEM0_API_KEY")
memory_client = MemoryClient(api_key=mem0_api_key)

# 计费常量
BILLING_UNIT_TOKENS = 1
MEM0_SEARCH_MODEL_ID = "rag"
MEM0_ADD_MODEL_ID = "rag"

# [新增] 定义无意义的停用短语集合 (全小写处理)
STOP_PHRASES = {
    # --- 1. 确认与应答 (Affirmation) ---
    "好的", "好", "好滴", "好哒", "好嘞", "行", "行吧", "可以", "可", "ok", "okay", "okk", "k", "kk",
    "收到", "收", "get", "got it", "roger", "copy",
    "明白", "明白了", "了解", "知道了", "懂了", "懂", "i see", "understood",
    "没问题", "没事", "无", "没有", "no problem", "np",
    "对", "对的", "是的", "是", "没错", "确实", "correct", "right", "yes", "yep", "yeah", "yup",

    # --- 2. 礼貌与感谢 (Politeness) ---
    "谢谢", "谢了", "多谢", "感谢", "十分感谢", "非常感谢", "thanks", "thx", "tks", "ty", "thank you",
    "不客气", "不用谢", "没事", "没关系", "you are welcome", "welcome",
    "抱歉", "对不起", "不好意思", "sorry", "sry",

    # --- 3. 寒暄与告别 (Greetings & Farewells) ---
    "你好", "您好", "嗨", "哈喽", "嘿", "喂", "hi", "hello", "hey", "hola",
    "再见", "拜拜", "拜", "88", "886", "晚安", "早安", "回见", "bye", "goodbye", "cya", "see ya", "good night", "gn",

    # --- 4. 情绪与感叹 (Emotions) ---
    "哈哈", "哈哈哈哈", "呵呵", "嘿嘿", "嘻嘻", "lol", "lmao", "rofl",
    "牛", "牛逼", "厉害", "666", "强", "太强了", "cool", "wow", "nice", "awesome", "good", "great",
    "啊", "哦", "噢", "嗯", "嗯嗯", "嗯呢", "额", "呃", "oh", "ah", "um", "hmm",

    # --- 5. 测试与无意义 (Noise) ---
    "测试", "test", "testing", "123", "1", "2", "在吗", "在?", "hello?",
    "继续", "continue", "go on"  # 这种指令通常是一次性的，不需要作为长期记忆存储
}

def is_noise_message(text: str) -> bool:
    """
    [新增] 基于规则的噪音过滤：
    1. 检查是否在停用词表中。
    2. 检查是否仅包含标点符号或表情。
    """
    if not text:
        return True
        
    clean_text = text.strip().lower()
    
    # 1. 精确匹配停用词 (避免 "好的方案是什么" 这种被误杀，所以用精确匹配)
    if clean_text in STOP_PHRASES:
        return True
        
    # 2. 检查是否包含有效字符 (中文、字母、数字)
    # 如果一句话里连一个汉字、字母或数字都没有 (比如 "。。。" 或 "😊😊")，视为噪音
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', clean_text):
        return True
        
    return False

def is_low_information(text: str, compression_threshold: float = 0.6, length_threshold: int = 5) -> bool:
    """基于压缩比的低信息过滤。"""
    # 如果长度极短，且不是停用词（停用词在 is_noise_message 处理），
    # 但为了保险起见，极短的内容通常也不具备记忆价值
    if len(text) < length_threshold:
        return True

    compressed = zlib.compress(text.encode("utf-8"))
    ratio = len(compressed) / len(text.encode("utf-8"))
    return ratio < compression_threshold


def _charge_mem0(user_id: str, model_id: str, type: str = "search"):
    """
    为 mem0 操作扣费。利用固定 token 单位和 ratio.py 中的定价得到固定费用。
    """
    if type == "search":
        deduct_balance(
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=1,
            completion_tokens=0,
            log_type="RAG",
        )
    else:
        deduct_balance(
            user_id=user_id,
            model_id=model_id,
            prompt_tokens=7,
            completion_tokens=0,
            log_type="RAG",
        )

async def mem0_search(user_id: str, chat_id: str, last_message: str) -> list[str]:
    """
    未来可替换为实际检索逻辑，返回若干相关记忆条目（字符串）。
    增加 chat_id 便于按会话窗口区分/隔离记忆。
    """
    try:
        # [优化] 如果只是纯寒暄，甚至不需要去 Search (可选，根据需求决定是否要在寒暄时也触发 RAG)
        # if is_noise_message(last_message): return []

        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID)
        
        log.info(f"mem0_search called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
        serach_rst = memory_client.search(
            query=last_message, filters={"user_id": user_id}
        )
        memories = serach_rst["results"] if "results" in serach_rst else serach_rst
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
    # [修改] 增加 is_noise_message 检查
    if is_noise_message(last_message) or is_low_information(last_message):
        log.info(f"mem0_search_and_add skipped adding noise/low-info message: {last_message}")
        return []

    try:
        # 先对检索计费
        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID, type="search")
        log.info(f"mem0_search called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
        
        serach_rst = memory_client.search(
            query=last_message, filters={"user_id": user_id}
        )
        
        if "results" not in serach_rst:
            log.info("mem0_search_and_add no results found, skipping add")
            memories = []
        else:
            log.info(f"mem0_search_and_add found {len(serach_rst['results'])} results")
            memories = serach_rst["results"]
            
        added_messages = [{"role": "user", "content": last_message}]
        
        # 执行添加
        memory_client.add(
            added_messages,
            user_id=user_id,
            enable_graph=True,
            async_mode=True,
            metadata={"session_id": chat_id},
        )
        
        # 再对添加计费
        _charge_mem0(user_id, MEM0_ADD_MODEL_ID, type="add")
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
        log.info(f"mem0_delete called with user_id: {user_id}, chat_id: {chat_id}")
        memory_client.delete(
            filters={"user_id": user_id}
        )
        return True
    except Exception as e:
        log.debug(f"Mem0 delete failed: {e}")
        return False
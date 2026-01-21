import os
import zlib
import re
import hashlib
import jieba.posseg as pseg  # [新增] 引入jieba词性标注
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

# mem0 API限制：10w token，预留余量设置为5w字符
MAX_MEM0_TEXT_LENGTH = 50000

# [配置] Jieba 词性过滤配置
# 定义高价值词性: 名词(n), 动词(v), 英文(eng), 专名(nr/ns/nt) 等
HIGH_VALUE_TAGS = {'n', 'v', 'vn', 'eng', 'nr', 'ns', 'nt', 'nz', 'vg', 'vd'}
# 信息密度阈值 (0.0 ~ 1.0)，低于此值视为水词
INFO_DENSITY_THRESHOLD = 0.3 

# [配置] 无意义的停用短语集合
STOP_PHRASES = {
    # --- 1. 确认与应答 ---
    "好的", "好", "好滴", "好哒", "好嘞", "行", "行吧", "可以", "可", "ok", "okay", "okk", "k", "kk",
    "收到", "收", "get", "got it", "roger", "copy",
    "明白", "明白了", "了解", "知道了", "懂了", "懂", "i see", "understood",
    "没问题", "没事", "无", "没有", "no problem", "np",
    "对", "对的", "是的", "是", "没错", "确实", "correct", "right", "yes", "yep", "yeah", "yup",

    # --- 2. 礼貌与感谢 ---
    "谢谢", "谢了", "多谢", "感谢", "十分感谢", "非常感谢", "thanks", "thx", "tks", "ty", "thank you",
    "不客气", "不用谢", "没事", "没关系", "you are welcome", "welcome",
    "抱歉", "对不起", "不好意思", "sorry", "sry",

    # --- 3. 寒暄与告别 ---
    "你好", "您好", "嗨", "哈喽", "嘿", "喂", "hi", "hello", "hey", "hola",
    "再见", "拜拜", "拜", "88", "886", "晚安", "早安", "回见", "bye", "goodbye", "cya", "see ya", "good night", "gn",

    # --- 4. 情绪与感叹 ---
    "哈哈", "哈哈哈哈", "呵呵", "嘿嘿", "嘻嘻", "lol", "lmao", "rofl",
    "牛", "牛逼", "厉害", "666", "强", "太强了", "cool", "wow", "nice", "awesome", "good", "great",
    "啊", "哦", "噢", "嗯", "嗯嗯", "嗯呢", "额", "呃", "oh", "ah", "um", "hmm",

    # --- 5. 测试与无意义 ---
    "测试", "test", "testing", "123", "1", "2", "在吗", "在?", "hello?",
    "继续", "continue", "go on"
}

def truncate_text_if_needed(text: str, max_length: int = MAX_MEM0_TEXT_LENGTH) -> str:
    """
    截断文本至指定长度，避免超过mem0 API限制
    如果需要截断，在末尾添加省略标记
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length - 10]  # 预留10个字符用于标记
    log.warning(f"Text truncated from {len(text)} to {max_length} chars")
    return truncated + "...[截断]"

def is_noise_message(text: str) -> bool:
    """基于规则的噪音过滤：停用词表 + 纯符号检测"""
    if not text:
        return True
    
    clean_text = text.strip().lower()
    
    # 1. 精确匹配停用词
    if clean_text in STOP_PHRASES:
        return True
    
    # 2. 简单的重复词检测 (如 "好的好的" -> "好的")
    if len(clean_text) <= 5: 
        for phrase in STOP_PHRASES:
            # 检查是否由停用词重复组成
            if clean_text == phrase * 2 or clean_text == phrase * 3:
                return True

    # 3. 检查是否包含有效字符 (中文、字母、数字)
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z0-9]', clean_text):
        return True
        
    return False

def is_low_information(text: str, compression_threshold: float = 0.6, length_threshold: int = 5) -> bool:
    """基于 Zlib 压缩比的过滤 (针对重复长文/乱码)"""
    if len(text) < length_threshold:
        return True  # 极短且通过了噪音检查的，通常由 density 检查再次把关

    compressed = zlib.compress(text.encode("utf-8"))
    ratio = len(compressed) / len(text.encode("utf-8"))
    return ratio < compression_threshold

def is_low_density(text: str) -> bool:
    """
    [新增] 基于 Jieba 词性的信息密度过滤
    计算：(名词+动词+外语) / 总词数
    """
    # 极短文本在前面已经被 is_noise_message 过滤，
    # 如果能走到这里且长度很短(如"Python教程")，通常是高价值的，避免被密度误杀
    if len(text) < 4: 
        return False 

    try:
        words = pseg.cut(text)
        high_val_count = 0
        total_count = 0
        
        for word, flag in words:
            # 过滤标点符号 (flag通常以w开头, x为非语素)
            if flag.startswith('w') or flag.startswith('x'):
                continue
                
            total_count += 1
            # 检查是否为高价值词性
            if any(flag.startswith(f) for f in HIGH_VALUE_TAGS):
                high_val_count += 1
        
        if total_count == 0:
            return True # 没有有效词汇，视为无信息
            
        density = high_val_count / total_count
        
        if density < INFO_DENSITY_THRESHOLD:
            log.info(f"Low density detected ({density:.2f}): {text}")
            return True
            
        return False
        
    except Exception as e:
        log.warning(f"Jieba processing failed: {e}, skipping density check")
        return False

def _charge_mem0(user_id: str, model_id: str, type: str = "search"):
    """
    为 mem0 操作扣费。
    """
    try:
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
    except Exception as e:
        from fastapi import HTTPException
        if isinstance(e, HTTPException) and e.status_code in (402, 403, 404):
            from open_webui.billing.core import convert_billing_exception_to_customized_error
            raise convert_billing_exception_to_customized_error(e)
        raise

async def mem0_search(user_id: str, chat_id: str, last_message: str) -> list[str]:
    """
    检索逻辑
    """
    try:
        # [可选] 也可以在这里加一层过滤，如果用户只是打招呼，就不必去查库了，省一次 Search 费用
        # if is_noise_message(last_message): return []

        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID)

        log.info(f"mem0_search called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
        serach_rst = memory_client.search(
            query=last_message,
            user_id=user_id
        )
        memories = serach_rst["results"] if "results" in serach_rst else serach_rst
        log.info(f"mem0_search found {len(memories)} memories")
        return [mem["text"] for mem in memories]
    except Exception as e:
        log.debug(f"Mem0 search failed: {e}")
        return []

async def mem0_search_and_add(user_id: str, chat_id: str, last_message: str, session_scope: bool = False) -> list[Dict]:
    """
    检索并添加记忆。

    Args:
        user_id: 用户ID
        chat_id: 聊天会话ID
        last_message: 最后一条消息
        session_scope: 是否限制搜索范围在当前会话内（True=仅当前会话，False=所有会话）
    """
    # [修改] 级联过滤：越便宜的检查越靠前
    # 1. 规则/停用词 (几乎0成本)
    if is_noise_message(last_message):
        log.debug(f"[mem: skip]Skipped (Noise): {last_message}")
        return []
    
    # 2. 压缩比 (极低成本)
    if is_low_information(last_message):
        log.debug(f"[mem: skip]Skipped (Low Info/Entropy): {last_message}")
        return []

    # 3. [新增] 词性密度 (低成本, CPU)
    if is_low_density(last_message):
        log.debug(f"[mem: skip]Skipped (Low Density): {last_message}")
        return []

    # --- 通过所有检查，准备调用 API ---
    try:
        # 先对检索计费
        _charge_mem0(user_id, MEM0_SEARCH_MODEL_ID, type="search")

        # 根据 session_scope 参数决定搜索范围
        if session_scope:
            log.info(f"[mem: search]mem0_search (session-scoped) called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
            serach_rst = memory_client.search(
                query=last_message,
                user_id=user_id,
                filters={"metadata": {"session_id": chat_id}}
            )
        else:
            log.info(f"[mem: search]mem0_search (all sessions) called with user_id: {user_id}, chat_id: {chat_id}, last_message: {last_message}")
            serach_rst = memory_client.search(
                query=last_message,
                user_id=user_id
            )
        
        if "results" not in serach_rst:
            log.info("[mem: search]mem0_search_and_add no results found, skipping add")
            memories = []
        else:
            log.info(f"[mem: search]mem0_search_and_add found {len(serach_rst['results'])} results")
            memories = serach_rst["results"]

        # 截断过长文本，避免超过mem0 API限制
        truncated_message = truncate_text_if_needed(last_message)
        added_messages = [{"role": "user", "content": truncated_message}]

        # 计算消息内容的哈希值，用于后续删除记忆时定位
        message_hash = hashlib.sha256(last_message.encode('utf-8')).hexdigest()

        # 执行添加
        memory_client.add(
            added_messages,
            user_id=user_id,
            enable_graph=True,
            async_mode=True,
            metadata={
                "session_id": chat_id,
                "message_hash": message_hash  # 添加消息哈希用于后续删除
            },
        )
        
        # 再对添加计费
        _charge_mem0(user_id, MEM0_ADD_MODEL_ID, type="add")
        log.info(f"[mem: add]mem0_add added message for user_id: {user_id}")
        return memories
    except Exception as e:
        log.error(f"[mem: search and add] search and add failed: {e}")
        return []
        
async def mem0_delete(user_id: str, chat_id: str) -> bool:
    """
    删除指定聊天会话的 mem0 记忆

    Args:
        user_id: 用户ID
        chat_id: 聊天会话ID

    Returns:
        bool: 删除成功返回 True
    """
    try:
        log.info(f"[mem: delete]mem0_delete called with user_id: {user_id}, chat_id: {chat_id}")

        # 先搜索该会话的所有记忆
        search_result = memory_client.search(
            query="*",  # 使用通配符查询所有
            user_id=user_id,
            filters={"metadata": {"session_id": chat_id}}  # metadata使用嵌套字典
        )

        # 获取记忆列表
        memories = search_result.get("results", [])

        # 逐个删除
        deleted_count = 0
        for memory in memories:
            try:
                memory_client.delete(memory_id=memory["id"])
                deleted_count += 1
            except Exception as e:
                log.warning(f"[mem: delete]Failed to delete memory {memory['id']}: {e}")

        log.info(f"[mem: delete]Successfully deleted {deleted_count} memories for chat_id: {chat_id}")
        return True
    except Exception as e:
        log.error(f"[mem: delete] mem0_delete failed: {e}")
        return False


async def mem0_delete_by_message_content(user_id: str, chat_id: str, message_content: str) -> bool:
    """
    根据消息内容删除对应的 mem0 记忆

    Args:
        user_id: 用户ID
        chat_id: 聊天会话ID
        message_content: 消息内容（用于计算哈希）

    Returns:
        bool: 删除成功返回 True
    """
    try:
        # 计算消息内容的哈希值
        message_hash = hashlib.sha256(message_content.encode('utf-8')).hexdigest()

        log.info(f"[mem: delete]mem0_delete_by_message_content called with user_id: {user_id}, chat_id: {chat_id}, hash: {message_hash[:16]}...")

        # 先搜索匹配的记忆
        search_result = memory_client.search(
            query="*",  # 使用通配符查询所有
            user_id=user_id,
            filters={
                "metadata": {
                    "session_id": chat_id,
                    "message_hash": message_hash
                }
            }
        )

        # 获取记忆列表
        memories = search_result.get("results", [])

        # 逐个删除
        deleted_count = 0
        for memory in memories:
            try:
                memory_client.delete(memory_id=memory["id"])
                deleted_count += 1
            except Exception as e:
                log.warning(f"[mem: delete]Failed to delete memory {memory['id']}: {e}")

        log.info(f"[mem: delete]Successfully deleted {deleted_count} memory(ies) for message_hash: {message_hash[:16]}...")
        return True
    except Exception as e:
        log.error(f"[mem: delete] mem0_delete_by_message_content failed: {e}")
        return False


async def mem0_delete_all(user_id: str) -> bool:
    """
    删除用户的所有 mem0 记忆

    Args:
        user_id: 用户ID

    Returns:
        bool: 删除成功返回 True
    """
    try:
        log.info(f"[mem: delete all]mem0_delete_all called with user_id: {user_id}")

        # 使用 delete_all() 方法删除该用户的所有记忆
        memory_client.delete_all(user_id=user_id)

        log.info(f"[mem: delete all]Successfully deleted all memories for user_id: {user_id}")
        return True
    except Exception as e:
        log.error(f"[mem: delete all] mem0_delete_all failed: {e}")
        return False
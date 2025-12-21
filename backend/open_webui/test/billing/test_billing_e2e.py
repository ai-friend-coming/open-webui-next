"""
计费模块端到端测试

测试真实 API 调用的计费流程，验证：
1. 流式响应 usage 解析
2. 非流式响应 usage 解析
3. 缓存 token 识别（如果 API 支持）
4. 费用计算准确性

运行方式：
    cd backend

    # 设置环境变量
    export E2E_API_BASE="https://yunwu.ai/v1"
    export E2E_API_KEY="sk-xxx"

    # 运行测试
    ./venv/bin/python -m pytest open_webui/test/billing/test_billing_e2e.py -v -s

注意：
    - 需要有效的 API key
    - 会产生实际的 API 调用费用
    - 建议使用便宜的模型进行测试
"""

import os
import json
import pytest
import httpx
import asyncio
from typing import AsyncIterator

# 使用 anyio 运行异步测试（仅 asyncio 后端）
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"

# 从环境变量获取配置
API_BASE = os.getenv("E2E_API_BASE", "https://yunwu.ai/v1")
API_KEY = os.getenv("E2E_API_KEY", "")

# 测试用模型（选择便宜的）
TEST_MODEL = os.getenv("E2E_TEST_MODEL", "gpt-4o-mini")


def skip_if_no_api_key():
    """如果没有 API key 则跳过测试"""
    if not API_KEY:
        pytest.skip("需要设置 E2E_API_KEY 环境变量")


# ============================================================================
# 辅助函数
# ============================================================================


async def call_chat_api_stream(
    messages: list,
    model: str = TEST_MODEL,
    max_tokens: int = 100,
    **kwargs,
) -> AsyncIterator[bytes]:
    """调用 Chat Completion API（流式）"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        **kwargs,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{API_BASE}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk


async def call_chat_api(
    messages: list,
    model: str = TEST_MODEL,
    max_tokens: int = 100,
    **kwargs,
) -> dict:
    """调用 Chat Completion API（非流式）"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        **kwargs,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# 端到端测试
# ============================================================================


class TestE2EStreamingUsage:
    """流式响应 usage 解析测试"""

    # @pytest.mark.asyncio (using anyio)
    async def test_stream_with_usage(self):
        """测试流式响应中的 usage 解析"""
        skip_if_no_api_key()

        from open_webui.billing.usage import (
            UsageInfo,
            parse_usage_from_sse_chunk,
            extract_delta_content,
        )

        messages = [{"role": "user", "content": "Say 'Hello' in 3 languages."}]

        accumulated_usage = UsageInfo()
        accumulated_content = []
        chunk_count = 0

        async for chunk in call_chat_api_stream(messages):
            chunk_count += 1

            # 解析 usage
            usage = parse_usage_from_sse_chunk(chunk)
            if usage and usage.has_data():
                accumulated_usage.merge_max(usage)
                print(f"\n[Chunk {chunk_count}] 解析到 usage:")
                print(f"  prompt_tokens: {usage.prompt_tokens}")
                print(f"  completion_tokens: {usage.completion_tokens}")
                print(f"  cached_tokens: {usage.cached_tokens}")
                print(f"  reasoning_tokens: {usage.reasoning_tokens}")

            # 累积内容
            content = extract_delta_content(chunk)
            if content:
                accumulated_content.append(content)

        # 验证结果
        full_content = "".join(accumulated_content)
        print(f"\n=== 流式响应结果 ===")
        print(f"总 chunk 数: {chunk_count}")
        print(f"内容: {full_content[:200]}...")
        print(f"累计 usage:")
        print(f"  prompt_tokens: {accumulated_usage.prompt_tokens}")
        print(f"  completion_tokens: {accumulated_usage.completion_tokens}")
        print(f"  cached_tokens: {accumulated_usage.cached_tokens}")
        print(f"  reasoning_tokens: {accumulated_usage.reasoning_tokens}")

        # 断言
        assert len(full_content) > 0, "应该有响应内容"

        # 检查 usage（有些 API 不支持流式 usage）
        if accumulated_usage.prompt_tokens > 0:
            print("✓ API 支持流式 usage")
            assert accumulated_usage.completion_tokens > 0, "应该有 completion tokens"
        else:
            print("⚠ API 不支持流式 usage（stream_options.include_usage）")
            print("  这种情况下需要依赖后备估算机制")

    # @pytest.mark.asyncio (using anyio)
    async def test_stream_cost_calculation(self):
        """测试流式响应的费用计算（含后备估算）"""
        skip_if_no_api_key()

        from open_webui.billing.usage import UsageInfo, parse_usage_from_sse_chunk, extract_delta_content
        from open_webui.billing.core import calculate_cost_with_usage, estimate_completion_tokens

        messages = [{"role": "user", "content": "Count from 1 to 10."}]

        accumulated_usage = UsageInfo()
        accumulated_content = []

        async for chunk in call_chat_api_stream(messages, max_tokens=50):
            usage = parse_usage_from_sse_chunk(chunk)
            if usage and usage.has_data():
                accumulated_usage.merge_max(usage)
            # 累积内容用于后备估算
            content = extract_delta_content(chunk)
            if content:
                accumulated_content.append(content)

        full_content = "".join(accumulated_content)

        # 如果 API 不返回 usage，使用后备估算
        if not accumulated_usage.has_data() and full_content:
            print("⚠ API 不返回流式 usage，使用后备估算")
            estimated_completion = estimate_completion_tokens(full_content, TEST_MODEL)
            # 简单估算 prompt tokens（实际应用中会用 tiktoken）
            estimated_prompt = len(messages[0]["content"]) // 4 + 10
            accumulated_usage = UsageInfo(
                prompt_tokens=estimated_prompt,
                completion_tokens=estimated_completion,
            )

        # 计算费用
        cost = calculate_cost_with_usage(TEST_MODEL, accumulated_usage)

        print(f"\n=== 费用计算结果 ===")
        print(f"模型: {TEST_MODEL}")
        print(f"prompt_tokens: {accumulated_usage.prompt_tokens}")
        print(f"completion_tokens: {accumulated_usage.completion_tokens}")
        print(f"内容长度: {len(full_content)} 字符")
        print(f"费用: {cost / 10000:.6f} 元 ({cost} 毫)")

        assert cost > 0, "费用应该大于 0（通过 API 或后备估算）"


class TestE2ENonStreamingUsage:
    """非流式响应 usage 解析测试"""

    # @pytest.mark.asyncio (using anyio)
    async def test_non_stream_usage(self):
        """测试非流式响应的 usage 解析"""
        skip_if_no_api_key()

        from open_webui.billing.usage import parse_usage
        from open_webui.billing.core import calculate_cost_with_usage

        messages = [{"role": "user", "content": "What is 2+2?"}]

        # 非流式调用
        response = await call_chat_api(messages, max_tokens=50)

        # 验证响应结构
        assert "usage" in response, "响应应该包含 usage"
        assert "choices" in response, "响应应该包含 choices"

        # 解析 usage
        usage_dict = response["usage"]
        usage_info = parse_usage(usage_dict)

        print(f"\n=== 非流式响应结果 ===")
        print(f"原始 usage: {json.dumps(usage_dict, indent=2)}")
        print(f"解析后:")
        print(f"  prompt_tokens: {usage_info.prompt_tokens}")
        print(f"  completion_tokens: {usage_info.completion_tokens}")
        print(f"  cached_tokens: {usage_info.cached_tokens}")
        print(f"  reasoning_tokens: {usage_info.reasoning_tokens}")

        # 计算费用
        cost = calculate_cost_with_usage(TEST_MODEL, usage_info)
        print(f"费用: {cost / 10000:.6f} 元")

        # 断言
        assert usage_info.prompt_tokens > 0
        assert usage_info.completion_tokens > 0


class TestE2ECacheTokens:
    """缓存 token 测试（需要 API 支持）"""

    # @pytest.mark.asyncio (using anyio)
    async def test_repeated_request_may_cache(self):
        """
        重复请求可能触发缓存

        注意：不是所有 API 都支持缓存，这个测试主要验证解析逻辑
        """
        skip_if_no_api_key()

        from open_webui.billing.usage import UsageInfo, parse_usage_from_sse_chunk
        from open_webui.billing.core import calculate_cost_with_usage

        # 使用较长的系统提示增加缓存可能性
        long_system_prompt = """You are a helpful assistant. """ * 50

        messages = [
            {"role": "system", "content": long_system_prompt},
            {"role": "user", "content": "Hi"},
        ]

        results = []

        # 发送两次相同请求
        for i in range(2):
            accumulated_usage = UsageInfo()

            async for chunk in call_chat_api_stream(messages, max_tokens=20):
                usage = parse_usage_from_sse_chunk(chunk)
                if usage and usage.has_data():
                    accumulated_usage.merge_max(usage)

            cost = calculate_cost_with_usage(TEST_MODEL, accumulated_usage)
            results.append({
                "request": i + 1,
                "prompt_tokens": accumulated_usage.prompt_tokens,
                "cached_tokens": accumulated_usage.cached_tokens,
                "completion_tokens": accumulated_usage.completion_tokens,
                "cost": cost,
            })

            print(f"\n请求 {i + 1}:")
            print(f"  prompt_tokens: {accumulated_usage.prompt_tokens}")
            print(f"  cached_tokens: {accumulated_usage.cached_tokens}")
            print(f"  completion_tokens: {accumulated_usage.completion_tokens}")
            print(f"  费用: {cost / 10000:.6f} 元")

            # 短暂等待
            await asyncio.sleep(0.5)

        # 如果第二次有缓存命中，cached_tokens 应该 > 0
        if results[1]["cached_tokens"] > 0:
            print(f"\n缓存命中！节省 tokens: {results[1]['cached_tokens']}")
            # 验证缓存导致费用降低
            assert results[1]["cost"] <= results[0]["cost"], "缓存应该降低费用"
        else:
            print("\n该 API 可能不支持缓存或缓存未命中")


class TestE2EBillingStreamWrapper:
    """BillingStreamWrapper 集成测试"""

    # @pytest.mark.asyncio (using anyio)
    async def test_billing_stream_wrapper(self):
        """测试 BillingStreamWrapper 的完整流程（含后备估算验证）"""
        skip_if_no_api_key()

        from open_webui.billing.stream import BillingStreamWrapper
        from open_webui.billing.usage import parse_usage_from_sse_chunk, extract_delta_content

        messages = [{"role": "user", "content": "Say hello!"}]

        # 创建模拟的 BillingContext（不实际操作数据库）
        class MockBillingContext:
            def __init__(self):
                self.user_id = "test_user"
                self.has_usage_data = False
                self.accumulated_content = ""
                self._usage_info = None

            def update_usage(self, prompt, completion):
                self.has_usage_data = True
                print(f"update_usage called: prompt={prompt}, completion={completion}")

            def update_usage_info(self, usage_info):
                self.has_usage_data = True
                self._usage_info = usage_info
                print(f"update_usage_info called: {usage_info}")

            async def settle(self):
                print("settle called")

        mock_billing = MockBillingContext()

        # 获取原始流
        async def get_stream():
            async for chunk in call_chat_api_stream(messages, max_tokens=50):
                yield chunk

        # 用 BillingStreamWrapper 包装
        wrapper = BillingStreamWrapper(
            stream=get_stream(),
            billing_context=mock_billing,
        )

        # 消费流并记录所有 chunks
        all_chunks = []
        accumulated_content = []
        async for chunk in wrapper:
            all_chunks.append(chunk)
            # 手动验证最后几个 chunk 是否包含 usage
            try:
                usage = parse_usage_from_sse_chunk(chunk)
                if usage and usage.has_data():
                    print(f"[Debug] Found usage in chunk: {usage}")
            except:
                pass
            # 累积内容
            content = extract_delta_content(chunk)
            if content:
                accumulated_content.append(content)

        full_content = "".join(accumulated_content)

        print(f"\n=== BillingStreamWrapper 测试结果 ===")
        print(f"Total chunks: {len(all_chunks)}")
        print(f"Content length: {len(full_content)} chars")
        print(f"has_usage_data: {mock_billing.has_usage_data}")
        if mock_billing._usage_info:
            print(f"usage_info: prompt={mock_billing._usage_info.prompt_tokens}, "
                  f"completion={mock_billing._usage_info.completion_tokens}")

        # 检查最后一个 chunk
        if all_chunks:
            last_chunk = all_chunks[-1]
            print(f"Last chunk: {last_chunk[:200] if len(last_chunk) > 200 else last_chunk}")

        # 验证 wrapper 内部状态
        print(f"wrapper._usage: {wrapper._usage}")
        print(f"wrapper._usage.has_data(): {wrapper._usage.has_data()}")
        print(f"wrapper._accumulated_content length: {len(wrapper._accumulated_content)}")

        # 验证后备机制
        if mock_billing.has_usage_data:
            print("✓ API 返回了 usage，BillingStreamWrapper 正确传递给 BillingContext")
        elif mock_billing.accumulated_content:
            print("✓ API 未返回 usage，但后备机制传递了累计内容")
            print(f"  accumulated_content: {mock_billing.accumulated_content[:100]}...")
        elif len(wrapper._accumulated_content) > 0:
            print("✓ wrapper 累计了内容（后备估算可用）")
        else:
            print("⚠ 没有 usage 也没有累计内容")

        # 核心断言：要么有 usage 数据，要么有累计内容可供后备估算
        assert mock_billing.has_usage_data or len(wrapper._accumulated_content) > 0, \
            "应该有 usage 数据或累计内容用于后备估算"

        # 验证有响应内容
        assert len(full_content) > 0, "应该有响应内容"


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    # 从命令行参数或环境变量获取配置
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        sys.exit(0)

    print(f"API Base: {API_BASE}")
    print(f"API Key: {'已设置' if API_KEY else '未设置'}")
    print(f"Test Model: {TEST_MODEL}")

    if not API_KEY:
        print("\n请设置环境变量后运行测试:")
        print('  export E2E_API_KEY="sk-xxx"')
        print('  export E2E_API_BASE="https://yunwu.ai/v1"')
        sys.exit(1)

    pytest.main([__file__, "-v", "-s"])

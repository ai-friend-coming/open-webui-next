"""
计费模块测试

测试范围：
1. UsageInfo 解析（OpenAI/Claude/Gemini 格式）
2. SSE chunk 解析
3. 费用计算（基础、缓存token、推理token）
4. Token 估算函数

运行方式：
    cd backend
    python -m pytest open_webui/test/billing/test_billing.py -v
"""

import pytest
import json

# ============================================================================
# 1. UsageInfo 解析测试
# ============================================================================


class TestUsageInfoParsing:
    """测试 usage 解析功能"""

    def test_parse_openai_basic(self):
        """OpenAI 基础格式"""
        from open_webui.billing.usage import parse_usage

        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        info = parse_usage(usage)

        assert info.prompt_tokens == 100
        assert info.completion_tokens == 50
        assert info.cached_tokens == 0
        assert info.reasoning_tokens == 0
        assert info.total_tokens == 150

    def test_parse_openai_with_details(self):
        """OpenAI 详细格式（含 cached_tokens, reasoning_tokens）"""
        from open_webui.billing.usage import parse_usage

        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": {
                "cached_tokens": 800,
                "audio_tokens": 0,
            },
            "completion_tokens_details": {
                "reasoning_tokens": 200,
                "audio_tokens": 0,
            },
        }
        info = parse_usage(usage)

        assert info.prompt_tokens == 1000
        assert info.completion_tokens == 500
        assert info.cached_tokens == 800
        assert info.reasoning_tokens == 200
        assert info.total_prompt_tokens == 1000 + 800  # prompt + cached
        assert info.total_completion_tokens == 500 + 200  # completion + reasoning

    def test_parse_claude_format(self):
        """Claude 格式（input_tokens/output_tokens）"""
        from open_webui.billing.usage import parse_usage

        usage = {
            "input_tokens": 2000,
            "output_tokens": 800,
            "cache_read_input_tokens": 1500,
            "cache_creation_input_tokens": 100,
        }
        info = parse_usage(usage)

        assert info.prompt_tokens == 2000
        assert info.completion_tokens == 800
        assert info.cached_tokens == 1500
        assert info.cache_creation_tokens == 100

    def test_parse_gemini_format(self):
        """Gemini 格式（含 thoughts_token_count）"""
        from open_webui.billing.usage import parse_usage

        usage = {
            "prompt_tokens": 500,
            "candidates_token_count": 300,
            "thoughts_token_count": 150,
        }
        info = parse_usage(usage)

        assert info.prompt_tokens == 500
        assert info.completion_tokens == 300
        assert info.reasoning_tokens == 150

    def test_parse_empty_usage(self):
        """空 usage 处理"""
        from open_webui.billing.usage import parse_usage

        info = parse_usage(None)
        assert info.prompt_tokens == 0
        assert info.completion_tokens == 0
        assert not info.has_data()

        info = parse_usage({})
        assert not info.has_data()

    def test_usage_info_merge_max(self):
        """UsageInfo.merge_max() 合并测试"""
        from open_webui.billing.usage import UsageInfo

        info1 = UsageInfo(prompt_tokens=100, completion_tokens=50)
        info2 = UsageInfo(prompt_tokens=80, completion_tokens=60, cached_tokens=20)

        info1.merge_max(info2)

        assert info1.prompt_tokens == 100  # max(100, 80)
        assert info1.completion_tokens == 60  # max(50, 60)
        assert info1.cached_tokens == 20  # max(0, 20)


# ============================================================================
# 2. SSE Chunk 解析测试
# ============================================================================


class TestSSEParsing:
    """测试 SSE 流式响应解析"""

    def test_parse_sse_with_usage(self):
        """解析包含 usage 的 SSE chunk"""
        from open_webui.billing.usage import parse_usage_from_sse_chunk

        chunk = b'data: {"id":"chatcmpl-123","choices":[],"usage":{"prompt_tokens":100,"completion_tokens":50}}\n\n'
        info = parse_usage_from_sse_chunk(chunk)

        assert info is not None
        assert info.prompt_tokens == 100
        assert info.completion_tokens == 50

    def test_parse_sse_without_usage(self):
        """解析不包含 usage 的 SSE chunk"""
        from open_webui.billing.usage import parse_usage_from_sse_chunk

        chunk = b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"Hello"}}]}\n\n'
        info = parse_usage_from_sse_chunk(chunk)

        assert info is None

    def test_parse_sse_done(self):
        """解析 [DONE] 消息"""
        from open_webui.billing.usage import parse_usage_from_sse_chunk

        chunk = b"data: [DONE]\n\n"
        info = parse_usage_from_sse_chunk(chunk)

        assert info is None

    def test_parse_sse_with_details(self):
        """解析包含详细 usage 的 SSE chunk"""
        from open_webui.billing.usage import parse_usage_from_sse_chunk

        usage_data = {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 800},
            "completion_tokens_details": {"reasoning_tokens": 200},
        }
        chunk = f'data: {{"usage": {json.dumps(usage_data)}}}\n\n'.encode()
        info = parse_usage_from_sse_chunk(chunk)

        assert info is not None
        assert info.cached_tokens == 800
        assert info.reasoning_tokens == 200

    def test_extract_delta_content(self):
        """提取流式内容"""
        from open_webui.billing.usage import extract_delta_content

        chunk = b'data: {"choices":[{"delta":{"content":"Hello, world!"}}]}\n\n'
        content = extract_delta_content(chunk)

        assert content == "Hello, world!"

    def test_extract_reasoning_content(self):
        """提取推理内容"""
        from open_webui.billing.usage import extract_delta_content

        chunk = b'data: {"choices":[{"delta":{"reasoning_content":"Let me think..."}}]}\n\n'
        content = extract_delta_content(chunk)

        assert content == "Let me think..."

    def test_extract_multiple_lines(self):
        """解析多行 SSE"""
        from open_webui.billing.usage import extract_delta_content

        chunk = b'data: {"choices":[{"delta":{"content":"A"}}]}\ndata: {"choices":[{"delta":{"content":"B"}}]}\n'
        content = extract_delta_content(chunk)

        assert content == "AB"


# ============================================================================
# 3. 费用计算测试
# ============================================================================


class TestCostCalculation:
    """测试费用计算"""

    def test_calculate_cost_basic(self):
        """基础费用计算"""
        from open_webui.billing.core import calculate_cost

        # 假设模型价格：输入 30元/M，输出 60元/M (300000毫/M, 600000毫/M)
        # 1000 prompt + 500 completion
        # 费用 = 1000/1M * 300000 + 500/1M * 600000 = 0.3 + 0.3 = 0.6元 = 6000毫
        # 由于使用默认价格，实际值可能不同，这里主要验证计算逻辑

        cost = calculate_cost("gpt-4o", 1000, 500)
        assert cost > 0
        assert isinstance(cost, int)

    def test_calculate_cost_with_usage_cached(self):
        """包含缓存 token 的费用计算"""
        from open_webui.billing.core import calculate_cost_with_usage, CACHE_TOKEN_RATIO
        from open_webui.billing.usage import UsageInfo

        # 缓存 token 按 10% 价格计费
        usage = UsageInfo(
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=900,  # 大量缓存命中
        )

        cost_with_cache = calculate_cost_with_usage("gpt-4o", usage)

        # 对比不使用缓存的费用
        usage_no_cache = UsageInfo(
            prompt_tokens=1000,  # 100 + 900
            completion_tokens=50,
        )
        cost_no_cache = calculate_cost_with_usage("gpt-4o", usage_no_cache)

        # 使用缓存应该更便宜
        assert cost_with_cache < cost_no_cache
        print(f"缓存节省: {(cost_no_cache - cost_with_cache) / 10000:.4f}元")

    def test_calculate_cost_with_reasoning(self):
        """包含推理 token 的费用计算"""
        from open_webui.billing.core import calculate_cost_with_usage
        from open_webui.billing.usage import UsageInfo

        usage = UsageInfo(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=500,  # 大量推理
        )

        cost = calculate_cost_with_usage("gpt-4o", usage)
        assert cost > 0

        # 推理 token 按输出价格计费，所以费用应该比只有 50 completion 高
        usage_no_reasoning = UsageInfo(
            prompt_tokens=100,
            completion_tokens=50,
        )
        cost_no_reasoning = calculate_cost_with_usage("gpt-4o", usage_no_reasoning)

        assert cost > cost_no_reasoning

    def test_minimum_cost(self):
        """最小费用测试（至少 1 毫）"""
        from open_webui.billing.core import calculate_cost

        # 极小的 token 数，应该至少扣 1 毫
        cost = calculate_cost("gpt-4o-mini", 1, 1)
        assert cost >= 1


# ============================================================================
# 4. Token 估算测试
# ============================================================================


class TestTokenEstimation:
    """测试 token 估算功能"""

    def test_estimate_prompt_tokens_text(self):
        """文本消息的 token 估算"""
        from open_webui.billing.core import estimate_prompt_tokens

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

        tokens = estimate_prompt_tokens(messages, "gpt-4o")
        assert tokens > 0
        assert tokens < 100  # 这么短的消息不应该超过 100 tokens

    def test_estimate_prompt_tokens_multimodal(self):
        """多模态消息的 token 估算"""
        from open_webui.billing.core import estimate_prompt_tokens

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/image.jpg"},
                    },
                ],
            }
        ]

        tokens = estimate_prompt_tokens(messages, "gpt-4o")
        # 应该包含图片 token（约 765）+ 文本 token
        assert tokens > 700

    def test_estimate_completion_tokens(self):
        """Completion token 估算"""
        from open_webui.billing.core import estimate_completion_tokens

        content = "This is a test response with some content."
        tokens = estimate_completion_tokens(content, "gpt-4o")

        assert tokens > 0
        assert tokens < 50  # 这么短的文本不应该超过 50 tokens

    def test_estimate_image_tokens(self):
        """图片 token 估算"""
        from open_webui.billing.core import estimate_image_tokens

        image_item = {"type": "image_url", "image_url": {"url": "test.jpg"}}

        # GPT-4o 使用 tile-based
        tokens_gpt4o = estimate_image_tokens(image_item, "gpt-4o")
        assert tokens_gpt4o == 765

        # Claude 使用像素计费
        tokens_claude = estimate_image_tokens(image_item, "claude-3-opus")
        assert tokens_claude == 1500


# ============================================================================
# 5. 常量和配置测试
# ============================================================================


class TestConstants:
    """测试常量配置"""

    def test_cache_token_ratio(self):
        """缓存 token 比例"""
        from open_webui.billing.core import CACHE_TOKEN_RATIO

        assert CACHE_TOKEN_RATIO == 0.1  # 10%

    def test_trust_quota_threshold(self):
        """信任额度阈值"""
        from open_webui.billing.core import TRUST_QUOTA_THRESHOLD

        assert TRUST_QUOTA_THRESHOLD == 1000  # 0.1元


# ============================================================================
# 6. 集成场景测试
# ============================================================================


class TestIntegrationScenarios:
    """集成场景测试"""

    def test_full_openai_stream_flow(self):
        """模拟完整的 OpenAI 流式响应解析流程"""
        from open_webui.billing.usage import (
            UsageInfo,
            parse_usage_from_sse_chunk,
            extract_delta_content,
        )

        # 模拟流式响应的多个 chunk
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"!"}}]}\n\n',
            b'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":3}}\n\n',
            b"data: [DONE]\n\n",
        ]

        accumulated_usage = UsageInfo()
        accumulated_content = []

        for chunk in chunks:
            # 解析 usage
            usage = parse_usage_from_sse_chunk(chunk)
            if usage and usage.has_data():
                accumulated_usage.merge_max(usage)

            # 累积内容
            content = extract_delta_content(chunk)
            if content:
                accumulated_content.append(content)

        # 验证结果
        assert accumulated_usage.prompt_tokens == 10
        assert accumulated_usage.completion_tokens == 3
        assert "".join(accumulated_content) == "Hello world!"

    def test_claude_usage_with_cache(self):
        """Claude 缓存场景"""
        from open_webui.billing.usage import parse_usage
        from open_webui.billing.core import calculate_cost_with_usage

        # Claude 响应中的 usage
        usage_dict = {
            "input_tokens": 5000,
            "output_tokens": 1000,
            "cache_read_input_tokens": 4500,  # 90% 缓存命中
            "cache_creation_input_tokens": 0,
        }

        usage = parse_usage(usage_dict)

        # 计算费用
        cost = calculate_cost_with_usage("claude-3-opus", usage)

        # 验证缓存被正确识别
        assert usage.cached_tokens == 4500
        assert cost > 0

        print(f"Claude 缓存场景费用: {cost / 10000:.4f}元")

    def test_o1_reasoning_scenario(self):
        """o1 推理模型场景"""
        from open_webui.billing.usage import parse_usage
        from open_webui.billing.core import calculate_cost_with_usage

        # o1 模型的 usage（含大量 reasoning_tokens）
        usage_dict = {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "completion_tokens_details": {
                "reasoning_tokens": 5000,  # 大量推理
            },
        }

        usage = parse_usage(usage_dict)

        assert usage.reasoning_tokens == 5000

        cost = calculate_cost_with_usage("o1-preview", usage)
        print(f"o1 推理场景费用: {cost / 10000:.4f}元")


# ============================================================================
# 运行测试
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

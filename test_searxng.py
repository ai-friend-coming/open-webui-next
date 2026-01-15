#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SearXNG 搜索引擎测试脚本
用于验证 SearXNG 配置是否正常工作
"""

import sys
import io

# 设置标准输出编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
from datetime import datetime

# SearXNG 实例 URL
SEARXNG_URL = "https://searx.be/search"

def test_searxng(query="Python programming"):
    """测试 SearXNG 搜索功能"""

    print(f"\n{'='*60}")
    print(f"测试 SearXNG 搜索引擎")
    print(f"{'='*60}")
    print(f"实例 URL: {SEARXNG_URL}")
    print(f"搜索关键词: {query}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    try:
        # 构建请求参数
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
            "safesearch": "1",
            "language": "en-US",
            "time_range": "",
            "categories": "",
            "theme": "simple",
            "image_proxy": 0,
        }

        # 发送请求
        print("正在发送请求...")
        response = requests.get(
            SEARXNG_URL,
            headers={
                "User-Agent": "Cakumi RAG Bot",
                "Accept": "text/html",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            },
            params=params,
            timeout=10
        )

        # 检查响应状态
        response.raise_for_status()
        print(f"✅ 请求成功！状态码: {response.status_code}\n")

        # 解析 JSON 响应
        json_response = response.json()
        results = json_response.get("results", [])

        if not results:
            print("⚠️  没有找到搜索结果")
            return False

        # 显示搜索结果
        print(f"找到 {len(results)} 条搜索结果:\n")

        for i, result in enumerate(results[:5], 1):
            print(f"结果 {i}:")
            print(f"  标题: {result.get('title', 'N/A')}")
            print(f"  链接: {result.get('url', 'N/A')}")
            print(f"  摘要: {result.get('content', 'N/A')[:100]}...")
            print(f"  评分: {result.get('score', 0)}")
            print()

        print(f"{'='*60}")
        print("✅ SearXNG 配置测试成功！")
        print(f"{'='*60}\n")

        return True

    except requests.exceptions.Timeout:
        print("❌ 错误: 请求超时")
        print("   建议: 尝试更换其他 SearXNG 实例")
        return False

    except requests.exceptions.ConnectionError:
        print("❌ 错误: 无法连接到 SearXNG 实例")
        print("   建议: 检查网络连接或更换实例 URL")
        return False

    except requests.exceptions.HTTPError as e:
        print(f"❌ 错误: HTTP 错误 {e.response.status_code}")
        print(f"   响应内容: {e.response.text[:200]}")
        return False

    except json.JSONDecodeError:
        print("❌ 错误: 无法解析 JSON 响应")
        print("   建议: 检查 SearXNG 实例是否正常工作")
        return False

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {str(e)}")
        return False


def test_multiple_instances():
    """测试多个 SearXNG 公共实例"""

    instances = [
        "https://searx.be/search",
        "https://search.sapti.me/search",
        "https://searx.info/search",
        "https://searx.tiekoetter.com/search",
    ]

    print(f"\n{'='*60}")
    print("测试多个 SearXNG 公共实例")
    print(f"{'='*60}\n")

    working_instances = []

    for url in instances:
        global SEARXNG_URL
        SEARXNG_URL = url

        print(f"测试实例: {url}")

        try:
            response = requests.get(
                url,
                params={"q": "test", "format": "json"},
                timeout=5
            )

            if response.status_code == 200:
                print(f"  ✅ 可用 (响应时间: {response.elapsed.total_seconds():.2f}s)\n")
                working_instances.append(url)
            else:
                print(f"  ❌ 不可用 (状态码: {response.status_code})\n")

        except Exception as e:
            print(f"  ❌ 不可用 ({type(e).__name__})\n")

    print(f"{'='*60}")
    print(f"可用实例数: {len(working_instances)}/{len(instances)}")

    if working_instances:
        print(f"\n推荐使用: {working_instances[0]}")

    print(f"{'='*60}\n")

    return working_instances


if __name__ == "__main__":
    print("\n🔍 SearXNG 搜索引擎配置测试工具\n")

    # 测试多个实例
    working_instances = test_multiple_instances()

    if working_instances:
        # 使用第一个可用实例进行详细测试
        SEARXNG_URL = working_instances[0]
        test_searxng("Python programming")

        print("\n📝 配置建议:")
        print(f"   在 .env 文件中设置:")
        print(f"   SEARXNG_QUERY_URL={working_instances[0]}")
        print()
    else:
        print("\n❌ 所有测试的 SearXNG 实例都不可用")
        print("   建议:")
        print("   1. 检查网络连接")
        print("   2. 尝试自己部署 SearXNG 实例")
        print("   3. 使用其他搜索引擎（如 Brave Search）")
        print()

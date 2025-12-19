"""
计费比例配置

定价单位：毫/百万tokens
说明：1元 = 10000毫，精度为 0.0001元
换算：原价格（元/百万tokens）× 10000 = 毫/百万tokens
"""

# 默认定价配置（毫/百万tokens）, 优先采用数据库里的定价
DEFAULT_PRICING = {
    # OpenAI 模型
    "gpt-4o": {"input": 25000, "output": 100000},  # 2.5元/M -> 25000毫/M
    "gpt-4o-mini": {"input": 1500, "output": 6000},  # 0.15元/M -> 1500毫/M
    "gpt-4-turbo": {"input": 100000, "output": 300000},  # 10元/M -> 100000毫/M
    "gpt-3.5-turbo": {"input": 5000, "output": 15000},  # 0.5元/M -> 5000毫/M

    # Claude 模型
    "claude-3.5-sonnet": {"input": 30000, "output": 150000},  # 3元/M -> 30000毫/M
    "claude-3-opus": {"input": 150000, "output": 750000},  # 15元/M -> 150000毫/M
    "claude-3-sonnet": {"input": 30000, "output": 150000},  # 3元/M -> 30000毫/M
    "claude-3-haiku": {"input": 2500, "output": 12500},  # 0.25元/M -> 2500毫/M

    # Gemini 模型
    "gemini-1.5-pro": {"input": 35000, "output": 105000},  # 3.5元/M -> 35000毫/M
    "gemini-1.5-flash": {"input": 750, "output": 3000},  # 0.075元/M -> 750毫/M


    "rag": {"input": 5000000, "output": 0},  # 5元/M -> 50000毫/M
    # 默认价格（未配置的模型使用此价格）
    "default": {"input": 10000, "output": 20000},  # 1元/M -> 10000毫/M
}

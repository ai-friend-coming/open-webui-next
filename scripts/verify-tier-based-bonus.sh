#!/bin/bash
# 档位独立首充优惠功能验证脚本

echo "=========================================="
echo "档位独立首充优惠 - 功能验证"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# API 基础URL
API_URL="${API_URL:-http://localhost:8080}"
TOKEN="${ADMIN_TOKEN:-}"

echo "📍 API地址: $API_URL"
echo ""

# 检查1: 数据库表结构
echo "1️⃣ 检查数据库表结构..."
if command -v sqlite3 &> /dev/null; then
    DB_PATH="${DB_PATH:-backend/data/webui.db}"

    # 检查 tier_amount 字段是否存在
    TIER_COLUMN=$(sqlite3 "$DB_PATH" "PRAGMA table_info(first_recharge_bonus_log);" | grep "tier_amount")

    if [ -n "$TIER_COLUMN" ]; then
        echo -e "${GREEN}✅ tier_amount 字段已添加${NC}"
    else
        echo -e "${RED}❌ tier_amount 字段不存在，请运行数据库迁移${NC}"
    fi

    # 检查唯一索引
    INDEXES=$(sqlite3 "$DB_PATH" "PRAGMA index_list(first_recharge_bonus_log);")
    if echo "$INDEXES" | grep -q "uq_user_tier"; then
        echo -e "${GREEN}✅ 复合唯一索引已创建${NC}"
    else
        echo -e "${RED}❌ 复合唯一索引不存在${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  sqlite3 未安装，跳过数据库检查${NC}"
fi
echo ""

# 检查2: API接口可用性
echo "2️⃣ 检查API接口..."

# 检查公共配置接口
CONFIG_RESPONSE=$(curl -s "$API_URL/api/v1/first-recharge-bonus/config/public")
if echo "$CONFIG_RESPONSE" | grep -q "enabled"; then
    echo -e "${GREEN}✅ 配置接口正常${NC}"
    echo "   返回: $CONFIG_RESPONSE"
else
    echo -e "${RED}❌ 配置接口异常${NC}"
fi

# 检查档位资格接口（需要token）
if [ -n "$TOKEN" ]; then
    TIERS_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/v1/first-recharge-bonus/eligibility/tiers")
    if echo "$TIERS_RESPONSE" | grep -q "tiers"; then
        echo -e "${GREEN}✅ 档位资格接口正常${NC}"
        echo "   返回: $TIERS_RESPONSE"
    else
        echo -e "${RED}❌ 档位资格接口异常${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  未提供ADMIN_TOKEN，跳过档位资格接口检查${NC}"
    echo "   使用方法: ADMIN_TOKEN='your_token' ./verify-tier-based-bonus.sh"
fi
echo ""

# 检查3: 前端文件修改
echo "3️⃣ 检查前端文件..."

RECHARGE_CARD="src/lib/components/billing/RechargeCard.svelte"
if [ -f "$RECHARGE_CARD" ]; then
    if grep -q "checkTiersEligibility" "$RECHARGE_CARD"; then
        echo -e "${GREEN}✅ RechargeCard 已更新（包含 checkTiersEligibility）${NC}"
    else
        echo -e "${RED}❌ RechargeCard 未更新${NC}"
    fi

    if grep -q "tierEligibilityMap" "$RECHARGE_CARD"; then
        echo -e "${GREEN}✅ 档位资格映射已添加${NC}"
    else
        echo -e "${RED}❌ 档位资格映射缺失${NC}"
    fi
else
    echo -e "${RED}❌ RechargeCard.svelte 文件不存在${NC}"
fi

BILLING_API="src/lib/apis/billing/index.ts"
if [ -f "$BILLING_API" ]; then
    if grep -q "checkTiersEligibility" "$BILLING_API"; then
        echo -e "${GREEN}✅ billing API 已更新${NC}"
    else
        echo -e "${RED}❌ billing API 未更新${NC}"
    fi
else
    echo -e "${RED}❌ billing/index.ts 文件不存在${NC}"
fi
echo ""

# 检查4: 后端文件修改
echo "4️⃣ 检查后端文件..."

BILLING_MODEL="backend/open_webui/models/billing.py"
if [ -f "$BILLING_MODEL" ]; then
    if grep -q "has_participated_tier" "$BILLING_MODEL"; then
        echo -e "${GREEN}✅ billing 模型已更新（包含 has_participated_tier）${NC}"
    else
        echo -e "${RED}❌ billing 模型未更新${NC}"
    fi

    if grep -q "get_participated_tiers" "$BILLING_MODEL"; then
        echo -e "${GREEN}✅ get_participated_tiers 方法已添加${NC}"
    else
        echo -e "${RED}❌ get_participated_tiers 方法缺失${NC}"
    fi
else
    echo -e "${RED}❌ billing.py 文件不存在${NC}"
fi

BILLING_ROUTER="backend/open_webui/routers/billing.py"
if [ -f "$BILLING_ROUTER" ]; then
    if grep -q "PRESET_TIERS" "$BILLING_ROUTER"; then
        echo -e "${GREEN}✅ 支付回调已更新（包含档位匹配）${NC}"
    else
        echo -e "${RED}❌ 支付回调未更新${NC}"
    fi
else
    echo -e "${RED}❌ billing.py 路由文件不存在${NC}"
fi
echo ""

# 总结
echo "=========================================="
echo "验证完成"
echo "=========================================="
echo ""
echo "📖 下一步操作："
echo "1. 确保所有检查项都是 ✅"
echo "2. 如有 ❌，请按照文档修复"
echo "3. 在管理后台启用首充优惠"
echo "4. 访问充值页面测试功能"
echo "5. 点击「🔍 调试」按钮查看详细状态"
echo ""
echo "📚 文档位置："
echo "   docs/TIER_BASED_FIRST_RECHARGE_IMPLEMENTATION.md"
echo ""

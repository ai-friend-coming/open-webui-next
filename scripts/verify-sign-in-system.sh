#!/bin/bash
# 每日签到系统功能验证脚本

echo "=========================================="
echo "每日签到系统 - 功能验证"
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

    # 检查 sign_in_log 表是否存在
    TABLE_EXISTS=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name='sign_in_log';" 2>/dev/null)

    if [ -n "$TABLE_EXISTS" ]; then
        echo -e "${GREEN}✅ sign_in_log 表已创建${NC}"

        # 检查表结构
        echo "   表结构："
        sqlite3 "$DB_PATH" "PRAGMA table_info(sign_in_log);" | while read line; do
            echo "   - $line"
        done
    else
        echo -e "${RED}❌ sign_in_log 表不存在，请运行数据库迁移${NC}"
        echo "   运行: cd backend && alembic upgrade head"
    fi

    # 检查唯一索引
    INDEXES=$(sqlite3 "$DB_PATH" "PRAGMA index_list(sign_in_log);" 2>/dev/null)
    if echo "$INDEXES" | grep -q "uq_user_sign_in_date"; then
        echo -e "${GREEN}✅ 用户-日期唯一索引已创建${NC}"
    else
        echo -e "${RED}❌ 用户-日期唯一索引不存在${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  sqlite3 未安装，跳过数据库检查${NC}"
fi
echo ""

# 检查2: API接口可用性
echo "2️⃣ 检查API接口..."

# 检查公共配置接口
CONFIG_RESPONSE=$(curl -s "$API_URL/api/v1/sign-in/config/public")
if echo "$CONFIG_RESPONSE" | grep -q "enabled"; then
    echo -e "${GREEN}✅ 公共配置接口正常${NC}"
    echo "   返回: $CONFIG_RESPONSE"
else
    echo -e "${RED}❌ 公共配置接口异常${NC}"
    echo "   返回: $CONFIG_RESPONSE"
fi

# 检查签到状态接口（需要token）
if [ -n "$TOKEN" ]; then
    STATUS_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/v1/sign-in/status")
    if echo "$STATUS_RESPONSE" | grep -q "has_signed_today"; then
        echo -e "${GREEN}✅ 签到状态接口正常${NC}"
        echo "   返回: $STATUS_RESPONSE"
    else
        echo -e "${RED}❌ 签到状态接口异常${NC}"
        echo "   返回: $STATUS_RESPONSE"
    fi

    # 检查管理员配置接口
    ADMIN_CONFIG_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$API_URL/api/v1/sign-in/config")
    if echo "$ADMIN_CONFIG_RESPONSE" | grep -q "mean"; then
        echo -e "${GREEN}✅ 管理员配置接口正常${NC}"
        echo "   返回: $ADMIN_CONFIG_RESPONSE"
    else
        echo -e "${RED}❌ 管理员配置接口异常${NC}"
        echo "   返回: $ADMIN_CONFIG_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️  未提供ADMIN_TOKEN，跳过需要认证的接口检查${NC}"
    echo "   使用方法: ADMIN_TOKEN='your_token' ./verify-sign-in-system.sh"
fi
echo ""

# 检查3: 后端文件
echo "3️⃣ 检查后端文件..."

SIGN_IN_MODEL="backend/open_webui/models/sign_in.py"
if [ -f "$SIGN_IN_MODEL" ]; then
    echo -e "${GREEN}✅ 签到数据模型已创建${NC}"

    if grep -q "has_signed_today" "$SIGN_IN_MODEL"; then
        echo -e "${GREEN}✅ has_signed_today 方法已添加${NC}"
    else
        echo -e "${RED}❌ has_signed_today 方法缺失${NC}"
    fi

    if grep -q "get_continuous_days" "$SIGN_IN_MODEL"; then
        echo -e "${GREEN}✅ get_continuous_days 方法已添加${NC}"
    else
        echo -e "${RED}❌ get_continuous_days 方法缺失${NC}"
    fi
else
    echo -e "${RED}❌ sign_in.py 模型文件不存在${NC}"
fi

SIGN_IN_ROUTER="backend/open_webui/routers/sign_in.py"
if [ -f "$SIGN_IN_ROUTER" ]; then
    echo -e "${GREEN}✅ 签到路由已创建${NC}"

    if grep -q "generate_reward_amount" "$SIGN_IN_ROUTER"; then
        echo -e "${GREEN}✅ 奖励金额生成函数已实现（正态分布）${NC}"
    else
        echo -e "${RED}❌ 奖励金额生成函数缺失${NC}"
    fi
else
    echo -e "${RED}❌ sign_in.py 路由文件不存在${NC}"
fi

# 检查路由注册
MAIN_PY="backend/open_webui/main.py"
if [ -f "$MAIN_PY" ]; then
    if grep -q "sign_in" "$MAIN_PY"; then
        echo -e "${GREEN}✅ 签到路由已在 main.py 注册${NC}"
    else
        echo -e "${RED}❌ 签到路由未在 main.py 注册${NC}"
    fi
else
    echo -e "${RED}❌ main.py 文件不存在${NC}"
fi
echo ""

# 检查4: 前端文件
echo "4️⃣ 检查前端文件..."

SIGN_IN_API="src/lib/apis/sign-in/index.ts"
if [ -f "$SIGN_IN_API" ]; then
    echo -e "${GREEN}✅ 签到 API 客户端已创建${NC}"

    if grep -q "signIn" "$SIGN_IN_API"; then
        echo -e "${GREEN}✅ signIn API 函数已定义${NC}"
    else
        echo -e "${RED}❌ signIn API 函数缺失${NC}"
    fi

    if grep -q "getSignInStatus" "$SIGN_IN_API"; then
        echo -e "${GREEN}✅ getSignInStatus API 函数已定义${NC}"
    else
        echo -e "${RED}❌ getSignInStatus API 函数缺失${NC}"
    fi
else
    echo -e "${RED}❌ sign-in/index.ts API 文件不存在${NC}"
fi

SIGN_IN_PANEL="src/lib/components/billing/SignInPanel.svelte"
if [ -f "$SIGN_IN_PANEL" ]; then
    echo -e "${GREEN}✅ 签到面板组件已创建${NC}"

    if grep -q "diceRolling" "$SIGN_IN_PANEL"; then
        echo -e "${GREEN}✅ 色子动画已实现${NC}"
    else
        echo -e "${RED}❌ 色子动画未实现${NC}"
    fi

    if grep -q "gradient-to-br from-pink" "$SIGN_IN_PANEL"; then
        echo -e "${GREEN}✅ 可爱风格设计已应用${NC}"
    else
        echo -e "${RED}❌ 可爱风格设计缺失${NC}"
    fi
else
    echo -e "${RED}❌ SignInPanel.svelte 组件文件不存在${NC}"
fi

BILLING_PAGE="src/routes/(app)/billing/+page.svelte"
if [ -f "$BILLING_PAGE" ]; then
    if grep -q "SignInPanel" "$BILLING_PAGE"; then
        echo -e "${GREEN}✅ 签到面板已集成到计费页面${NC}"
    else
        echo -e "${RED}❌ 签到面板未集成到计费页面${NC}"
    fi
else
    echo -e "${RED}❌ billing/+page.svelte 页面文件不存在${NC}"
fi

ADMIN_SETTINGS="src/lib/components/admin/Settings.svelte"
if [ -f "$ADMIN_SETTINGS" ]; then
    if grep -q "SignIn" "$ADMIN_SETTINGS"; then
        echo -e "${GREEN}✅ 签到设置已添加到管理后台${NC}"
    else
        echo -e "${RED}❌ 签到设置未添加到管理后台${NC}"
    fi
else
    echo -e "${RED}❌ Settings.svelte 文件不存在${NC}"
fi

ADMIN_SIGN_IN="src/lib/components/admin/Settings/SignIn.svelte"
if [ -f "$ADMIN_SIGN_IN" ]; then
    echo -e "${GREEN}✅ 管理后台签到配置组件已创建${NC}"
else
    echo -e "${RED}❌ SignIn.svelte 管理组件文件不存在${NC}"
fi
echo ""

# 总结
echo "=========================================="
echo "验证完成"
echo "=========================================="
echo ""
echo "📖 下一步操作："
echo "1. 确保所有检查项都是 ✅"
echo "2. 如有 ❌，请按照提示修复"
echo "3. 运行数据库迁移: cd backend && alembic upgrade head"
echo "4. 在管理后台 /admin/settings/sign-in 启用签到功能"
echo "5. 配置奖励参数（均值、标准差、最小/最大金额）"
echo "6. 访问 /billing 页面测试签到功能"
echo ""
echo "🎲 功能特性："
echo "- ✨ 每日签到获得随机奖励"
echo "- 🎲 色子滚动动画效果"
echo "- 📊 连续签到天数统计"
echo "- 🎁 正态分布奖励金额"
echo "- 💰 可配置奖励范围"
echo "- 🎨 可爱风格界面设计"
echo ""

#!/bin/bash
# 启用首充优惠的快速脚本

echo "正在启用首充优惠..."

# 获取管理员 token（需要先登录）
# 替换为你的管理员 token
ADMIN_TOKEN="your_admin_token_here"

# API 地址
API_URL="http://localhost:8080"

# 启用首充优惠配置
curl -X POST "${API_URL}/api/v1/first-recharge-bonus/config" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "rate": 20,
    "max_amount": 100
  }'

echo ""
echo "✅ 首充优惠已启用！"
echo "   - 返现比例：20%"
echo "   - 最高奖励：100元"

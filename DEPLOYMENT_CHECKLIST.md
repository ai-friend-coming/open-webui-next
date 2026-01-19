# 邀请系统部署检查清单

## ✅ 已完成的修改

### 1. 数据库迁移文件
- [x] 创建迁移文件: `m1n2o3p4q5r6_add_invite_system.py`
- [x] 修复迁移链: `down_revision` 改为 `add_sign_in_001`
- [x] 修复字段默认值: 使用 `server_default` 替代 `default`

### 2. 启动脚本自动迁移
- [x] 修改 `backend/start.sh`
- [x] 添加自动迁移命令: `alembic upgrade head`
- [x] 添加错误处理和提示信息

### 3. 迁移链结构
```
l6m7n8o9p0q1 (首充奖励日志表)
  ↓
tier_based_bonus_001 (档位制首充奖励)
  ↓
add_sign_in_001 (签到系统)
  ↓
m1n2o3p4q5r6 (邀请推广系统) ✅ 新增
```

## 📋 部署步骤

### 方式 1: Docker Compose 重启（推荐）

```bash
# 停止容器
docker-compose down

# 重建并启动（确保使用最新代码）
docker-compose up -d --build

# 查看日志，确认迁移成功
docker-compose logs -f open-webui-next
```

**预期日志输出：**
```
Running database migrations...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade add_sign_in_001 -> m1n2o3p4q5r6, Add invite system
Checking for users without invite codes...
INFO: Found 15 users without invite codes, generating...
SUCCESS: Generated invite codes for 15 users
```

**🆕 自动修复功能**：即使迁移的 backfill 逻辑失败，容器启动时也会自动检查并为缺少邀请码的用户生成邀请码。

### 方式 2: Docker 重启

```bash
# 重启容器
docker restart open-webui-next

# 查看日志
docker logs -f open-webui-next
```

### 方式 3: 手动触发迁移（如果自动迁移失败）

```bash
# 进入容器
docker exec -it open-webui-next bash

# 进入后端目录
cd /app/backend

# 检查当前迁移版本
python -m alembic current

# 执行迁移
python -m alembic upgrade head

# 再次检查版本（应显示 m1n2o3p4q5r6）
python -m alembic current

# 退出容器
exit

# 重启容器
docker restart open-webui-next
```

## ✅ 部署后验证

### 1. 检查容器日志

```bash
docker logs open-webui-next | grep -i "migration\|alembic"
```

**预期输出：**
- ✅ "Running database migrations..."
- ✅ "Running upgrade add_sign_in_001 -> m1n2o3p4q5r6"
- ❌ 不应该看到任何错误信息

### 2. 检查数据库表

```bash
# 连接数据库
docker exec -it open-webui-next psql $DATABASE_URL

# 检查邀请相关表
\dt invite*

# 应该看到：
# invite_rebate_log
# invite_stats

# 检查 user 表字段
\d user

# 应该包含：
# invite_code | character varying(8)
# invited_by  | character varying

# 退出
\q
```

### 3. 访问前端验证

访问应用 URL，检查：
- ✅ 首页能正常加载（不再显示 "Cakumi Backend Required"）
- ✅ 不应该有 500 错误
- ✅ 浏览器控制台没有 API 错误

### 4. 测试邀请功能

1. **管理员设置：**
   - 访问 `/admin/settings/invite`
   - 设置返现比例（默认 5%）
   - 保存配置

2. **用户注册：**
   - 访问 `/admin/settings/recharge-tiers`
   - 配置充值档位
   - 保存

3. **查看邀请信息：**
   - 访问 `/billing`
   - 应该能看到邀请面板
   - 显示专属邀请码

## 🚨 故障排查

### 问题 1: "column user.invite_code does not exist"

**原因：** 迁移未执行或执行失败

**解决：**
```bash
# 检查容器日志
docker logs open-webui-next | tail -100

# 手动执行迁移（参见方式 3）
```

### 问题 2: "Multiple heads in the revision graph"

**原因：** 迁移链冲突（已修复）

**解决：**
```bash
# 确保使用最新代码
git pull origin main

# 重建容器
docker-compose up -d --build
```

### 问题 3: 迁移执行但应用仍报错

**原因：** 可能是缓存问题

**解决：**
```bash
# 完全重启容器
docker-compose down
docker-compose up -d

# 清除浏览器缓存并刷新
```

### 问题 4: "Cakumi Backend Required" 错误

**原因：** 这是前端开发模式的错误，生产环境不应出现

**解决：**
- 确保访问的是后端服务的地址（如 `http://your-domain:8080`）
- 不要访问前端开发服务器（`http://localhost:5173`）

## 📊 迁移影响评估

### 性能影响
- **添加字段：** user 表新增 2 个字段（nullable，不锁表）
- **新建表：** 2 个小表（invite_rebate_log, invite_stats）
- **索引创建：** 7 个索引（在迁移时创建，对空表无影响）
- **预计耗时：** < 1 秒（数据库为空或用户量少时）

### 向后兼容性
- ✅ 所有新字段都是 nullable
- ✅ 不影响现有功能
- ✅ 可以安全回滚（如需）

### 数据安全
- ✅ 不会删除或修改现有数据
- ✅ 仅添加新的表和字段
- ✅ 建议在执行前备份数据库

## 🔄 回滚方案（如需）

```bash
# 进入容器
docker exec -it open-webui-next bash

# 回滚到签到系统版本
python -m alembic downgrade add_sign_in_001

# 退出并重启
exit
docker restart open-webui-next
```

**警告：** 回滚会删除所有邀请相关数据！

## 📝 修改文件清单

```
backend/
├── start.sh (修改 - 添加自动迁移)
└── open_webui/
    └── migrations/
        └── versions/
            └── m1n2o3p4q5r6_add_invite_system.py (修改 - 修复迁移链)

新增文档:
├── MIGRATION_GUIDE.md (新增)
└── DEPLOYMENT_CHECKLIST.md (新增 - 本文件)
```

## 🎯 下一步

部署完成后，可以：
1. 测试邀请码生成
2. 测试用户注册（使用邀请码）
3. 测试充值返现流程
4. 配置返现比例
5. 监控邀请统计数据

## 📞 支持

如有问题，请：
1. 检查容器日志：`docker logs open-webui-next`
2. 查看数据库状态：`docker exec -it open-webui-next psql $DATABASE_URL`
3. 参考 MIGRATION_GUIDE.md 详细说明

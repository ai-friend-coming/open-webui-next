# 数据库迁移指南

## 概述

本文档介绍如何运行数据库迁移，包括档位独立首充优惠和每日签到系统的数据库更新。

## 迁移内容

### 1. 档位独立首充优惠 (tier_based_bonus_001)

**修改内容**：
- 在 `first_recharge_bonus_log` 表添加 `tier_amount` 字段
- 将 `user_id` 唯一索引改为 `(user_id, tier_amount)` 复合唯一索引
- 支持每个充值档位独立的首充资格

**影响**：
- 现有用户的首充记录会自动迁移，`tier_amount` 设置为其 `recharge_amount`
- 用户可以在每个预设档位（10/50/100/200/500/1000元）享受一次首充优惠

### 2. 每日签到系统 (add_sign_in_001)

**修改内容**：
- 创建 `sign_in_log` 表
- 包含字段：`id`, `user_id`, `amount`, `sign_in_date`, `created_at`
- 复合唯一约束：`(user_id, sign_in_date)` 确保每天只能签到一次
- 索引：`user_id`, `created_at`

**影响**：
- 添加全新的每日签到功能
- 用户可以每天签到一次获得随机金额奖励

---

## 快速开始

### Windows 用户

直接运行自动化脚本：

```cmd
# 在项目根目录
cd C:\Users\cryan\Desktop\cakumi\open-webui-next

# 运行迁移脚本
scripts\run-migrations.bat
```

### Linux/Mac 用户

```bash
# 在项目根目录
cd /path/to/open-webui-next

# 给脚本添加执行权限
chmod +x scripts/run-migrations.sh

# 运行迁移脚本
./scripts/run-migrations.sh
```

---

## 手动运行迁移

如果自动化脚本无法运行，可以手动执行：

### 1. 进入 backend 目录

```bash
cd backend
```

### 2. 检查当前数据库版本

```bash
alembic current
```

### 3. 查看待执行的迁移

```bash
alembic history --verbose
```

### 4. 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 或者逐个执行
alembic upgrade tier_based_bonus_001
alembic upgrade add_sign_in_001
```

### 5. 验证迁移结果

```bash
alembic current
```

应该显示：`add_sign_in_001 (head)`

---

## 数据库连接配置

### PostgreSQL

确保设置正确的 `DATABASE_URL` 环境变量：

```bash
# Linux/Mac
export DATABASE_URL="postgresql://username:password@localhost:5432/database_name"

# Windows (PowerShell)
$env:DATABASE_URL="postgresql://username:password@localhost:5432/database_name"

# Windows (CMD)
set DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```

### SQLite

SQLite 数据库会自动使用 `backend/data/webui.db`，无需额外配置。

---

## 验证迁移成功

### 1. 检查数据库表结构

#### PostgreSQL

```sql
-- 检查 first_recharge_bonus_log 表
\d first_recharge_bonus_log

-- 应该能看到 tier_amount 字段和 idx_user_tier 索引

-- 检查 sign_in_log 表
\d sign_in_log

-- 应该能看到所有字段和索引
```

#### SQLite

```bash
sqlite3 backend/data/webui.db
```

```sql
-- 检查表结构
.schema first_recharge_bonus_log
.schema sign_in_log

-- 查看索引
.indexes first_recharge_bonus_log
.indexes sign_in_log

-- 退出
.quit
```

### 2. 测试 API 端点

启动后端服务后：

```bash
# 测试首充优惠配置接口
curl http://localhost:8080/api/v1/first-recharge-bonus/config/public

# 应该返回:
# {"enabled":false,"rate":0,"max_amount":0}

# 测试签到公开配置接口
curl http://localhost:8080/api/v1/sign-in/config/public

# 应该返回:
# {"enabled":false}
```

---

## 常见问题

### 问题 1：找不到 tier_amount 字段

**错误信息**：
```
column first_recharge_bonus_log.tier_amount does not exist
```

**解决方案**：
运行数据库迁移：`alembic upgrade head`

---

### 问题 2：迁移冲突

**错误信息**：
```
Can't locate revision identified by 'l6m7n8o9p0q1'
```

**解决方案**：

1. 检查迁移依赖关系：
```bash
alembic history
```

2. 如果找不到前置迁移版本，修改 `down_revision`：
```python
# 在 tier_based_first_recharge_bonus.py 中
down_revision = None  # 或实际存在的版本号
```

3. 重新运行迁移

---

### 问题 3：约束冲突

**错误信息**：
```
constraint "uq_first_recharge_bonus_log_user_id" of relation "first_recharge_bonus_log" does not exist
```

**解决方案**：

这是正常的，迁移脚本已经处理了这种情况。约束可能已经被删除或不存在，迁移会继续执行。

如果迁移失败，可以手动检查并删除旧约束：

```sql
-- PostgreSQL
ALTER TABLE first_recharge_bonus_log
DROP CONSTRAINT IF EXISTS uq_first_recharge_bonus_log_user_id;

-- 然后重新运行迁移
```

---

### 问题 4：数据库连接失败

**错误信息**：
```
could not connect to server: Connection refused
```

**解决方案**：

1. 确保数据库服务正在运行：
```bash
# PostgreSQL
sudo systemctl status postgresql
# 或
pg_isready

# 如果未运行，启动它
sudo systemctl start postgresql
```

2. 检查连接配置：
   - 主机名/IP 是否正确
   - 端口是否正确（PostgreSQL 默认 5432）
   - 用户名和密码是否正确
   - 数据库是否存在

---

## 回滚迁移

如果需要回滚迁移（慎用）：

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到特定版本
alembic downgrade tier_based_bonus_001

# 回滚所有迁移
alembic downgrade base
```

**警告**：回滚迁移会删除相应的表和字段，数据会丢失！

---

## 迁移依赖关系

```
base
  ↓
... (其他迁移)
  ↓
l6m7n8o9p0q1 (前置迁移)
  ↓
tier_based_bonus_001 (档位独立首充优惠)
  ↓
add_sign_in_001 (每日签到系统)
```

---

## 数据备份建议

在运行迁移前，强烈建议备份数据库：

### PostgreSQL

```bash
# 备份数据库
pg_dump -U username -d database_name > backup_$(date +%Y%m%d).sql

# 恢复（如果需要）
psql -U username -d database_name < backup_20260118.sql
```

### SQLite

```bash
# 备份数据库
cp backend/data/webui.db backend/data/webui.db.backup_$(date +%Y%m%d)

# 恢复（如果需要）
cp backend/data/webui.db.backup_20260118 backend/data/webui.db
```

---

## 联系支持

如果遇到无法解决的问题，请提供以下信息：

1. 数据库类型和版本（PostgreSQL/SQLite）
2. 完整的错误日志
3. `alembic current` 和 `alembic history` 的输出
4. 数据库表结构（`\d first_recharge_bonus_log` 的输出）

---

**最后更新**: 2026-01-18
**版本**: v1.0

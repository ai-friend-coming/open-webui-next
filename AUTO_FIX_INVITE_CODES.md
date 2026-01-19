# 邀请码自动修复功能

## ✨ 功能说明

容器启动时会**自动检查并修复**缺少邀请码的用户，无需手动干预。

## 🔄 工作流程

每次容器启动时（`start.sh`）：

1. **执行数据库迁移** → `alembic upgrade head`
2. **自动检查邀请码** → 检测是否有用户的 `invite_code` 为 NULL
3. **自动生成邀请码** → 为缺少邀请码的用户生成唯一的6-8位邀请码
4. **启动应用** → 所有用户都有邀请码后，正常启动服务

## 📋 部署步骤

只需重启容器即可：

```bash
# 停止容器
docker-compose down

# 重建并启动
docker-compose up -d --build

# 查看日志（确认自动修复执行）
docker-compose logs -f open-webui-next | grep -A 2 "invite codes"
```

## 🎯 预期日志输出

### 场景1：所有用户都有邀请码

```
Running database migrations...
Checking for users without invite codes...
INFO: All users have invite codes (checked 0 users)
```

### 场景2：有用户缺少邀请码（自动修复）

```
Running database migrations...
Checking for users without invite codes...
INFO: Found 15 users without invite codes, generating...
SUCCESS: Generated invite codes for 15 users
```

### 场景3：invite_code 字段还不存在（等待迁移）

```
Running database migrations...
INFO  [alembic.runtime.migration] Running upgrade add_sign_in_001 -> m1n2o3p4q5r6, Add invite system
Found 15 existing users without invite codes
Successfully generated invite codes for 15 users
Checking for users without invite codes...
INFO: All users have invite codes (checked 0 users)
```

## ⚙️ 技术细节

### 自动修复逻辑位置
`backend/start.sh` 第82-155行

### 执行时机
- 在 Alembic 迁移**之后**
- 在 Uvicorn 启动应用**之前**

### 安全性
- ✅ 检查表结构是否存在（避免在字段创建前执行）
- ✅ 使用事务保证原子性
- ✅ 冲突检测（确保邀请码唯一）
- ✅ 失败不影响启动（只记录警告日志）

### 幂等性
可以多次执行，不会重复生成邀请码：
- 已有邀请码的用户 → 跳过
- 缺少邀请码的用户 → 生成

## ✅ 验证修复成功

### 方法1：查看日志
```bash
docker logs open-webui-next | grep "invite codes"
```

应看到：
```
INFO: All users have invite codes (checked 0 users)
```
或
```
SUCCESS: Generated invite codes for 15 users
```

### 方法2：检查数据库
```bash
docker exec open-webui-next psql $DATABASE_URL -c \
  "SELECT COUNT(*) - COUNT(invite_code) as missing FROM \"user\";"
```

应返回 `missing = 0`

### 方法3：前端验证
访问 `/billing` 页面 → 邀请面板 → 应显示类似 `K3M7P9` 的邀请码

## 🐛 故障排查

### 问题：日志中没有看到 "Checking for users without invite codes"

**原因**：容器使用了旧版本的 `start.sh`

**解决**：
```bash
docker-compose down
docker-compose up -d --build  # 确保重新构建
```

### 问题：日志显示 "WARNING: Failed to auto-fix invite codes"

**原因**：数据库连接失败或权限不足

**解决**：
1. 检查数据库连接：`docker logs open-webui-next | grep DATABASE`
2. 检查数据库权限：用户需要 UPDATE 权限

### 问题：自动修复成功但前端还是显示 null

**原因**：浏览器缓存

**解决**：
1. 清除浏览器缓存
2. 硬刷新页面（Ctrl+Shift+R）
3. 或者登出重新登录

## 📊 与迁移文件的关系

### 迁移文件 (`m1n2o3p4q5r6_add_invite_system.py`)
- **首次部署**：创建表、添加字段、生成邀请码
- **执行一次**：Alembic 版本控制，不会重复执行

### 自动修复脚本 (`start.sh`)
- **每次启动**：检查并修复缺少邀请码的用户
- **执行多次**：幂等操作，安全可靠
- **兜底机制**：防止迁移 backfill 失败

## 🎯 适用场景

1. ✅ 初次部署邀请系统
2. ✅ 迁移 backfill 失败（字段添加成功但邀请码生成失败）
3. ✅ 数据损坏恢复（invite_code 字段被误清空）
4. ✅ 数据导入后修复（导入的用户数据缺少邀请码）

## 🚀 优势

- **零手动操作**：完全自动化
- **容器即配置**：代码即基础设施
- **高可靠性**：每次启动都会检查
- **生产友好**：失败不影响应用启动

---

**总结**：部署后无需任何手动操作，容器会自动确保所有用户都有邀请码！

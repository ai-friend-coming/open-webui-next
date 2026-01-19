# 数据库迁移指南

## 迁移链结构

当前数据库迁移链（按顺序）：

```
l6m7n8o9p0q1 (首充奖励日志表)
  ↓
tier_based_bonus_001 (档位制首充奖励)
  ↓
add_sign_in_001 (签到系统)
  ↓
m1n2o3p4q5r6 (邀请推广系统)
```

## 自动迁移（Docker 环境）

如果您的 Docker 工作流已配置自动迁移，只需重启容器：

```bash
# 方式 1: 重启容器
docker restart open-webui-next

# 方式 2: 使用 docker-compose
docker-compose restart open-webui-next

# 方式 3: 完全重建（确保使用最新代码）
docker-compose down
docker-compose up -d --build
```

容器启动时会自动执行 `alembic upgrade head` 命令。

## 手动迁移（如果自动迁移失败）

### 步骤 1: 进入容器

```bash
docker exec -it open-webui-next bash
```

### 步骤 2: 进入后端目录

```bash
cd /app/backend
```

### 步骤 3: 检查当前迁移状态

```bash
# 查看当前版本
alembic current

# 查看历史记录
alembic history

# 查看待执行的迁移
alembic heads
```

### 步骤 4: 执行迁移

```bash
# 升级到最新版本
alembic upgrade head

# 或者使用 Python 模块方式
python -m alembic upgrade head
```

### 步骤 5: 验证迁移

```bash
# 再次查看当前版本，应该显示 m1n2o3p4q5r6
alembic current

# 退出容器
exit
```

## 迁移内容说明

### m1n2o3p4q5r6 - 邀请推广系统

**新增表：**

1. **invite_rebate_log** - 邀请返现日志
   - id (主键)
   - inviter_id (邀请人ID，索引)
   - invitee_id (被邀请人ID，索引)
   - recharge_amount (充值金额，单位：毫)
   - rebate_amount (返现金额，单位：毫)
   - rebate_rate (返现比例，百分比)
   - inviter_balance_before (返现前余额)
   - inviter_balance_after (返现后余额)
   - recharge_log_id (关联的充值日志ID)
   - created_at (创建时间戳，纳秒，索引)

2. **invite_stats** - 邀请统计汇总
   - user_id (用户ID，主键)
   - total_invitees (累计邀请人数，默认0)
   - total_rebate_amount (累计返现金额，默认0)
   - last_rebate_at (最后返现时间)
   - updated_at (更新时间戳，索引)

**修改表：**

- **user** 表新增字段：
  - invite_code (邀请码，8位字符串，唯一索引)
  - invited_by (邀请人ID，索引)

## 常见问题排查

### 问题 1: "column user.invite_code does not exist"

**原因：** 迁移尚未执行

**解决：** 按照上述手动迁移步骤执行迁移

### 问题 2: "alembic: command not found"

**原因：** Python 环境问题

**解决：** 使用 `python -m alembic upgrade head`

### 问题 3: "Multiple heads in alembic"

**原因：** 迁移链有分支冲突

**解决：** 已在本次修复中解决，确保使用最新的迁移文件

### 问题 4: 迁移执行缓慢或超时

**原因：** 大表添加字段时锁表

**解决：**
- user 表的字段都是 nullable=True，不会锁表
- 如果仍有问题，可在低流量时段执行

## 回滚迁移（如需）

```bash
# 回滚到签到系统版本
alembic downgrade add_sign_in_001

# 回滚到档位奖励版本
alembic downgrade tier_based_bonus_001

# 回滚到首充日志版本
alembic downgrade l6m7n8o9p0q1
```

**警告：** 回滚会删除相关表和数据，请谨慎操作！

## 验证迁移成功

执行迁移后，可以通过以下方式验证：

```bash
# 方式 1: 在容器中连接数据库
docker exec -it open-webui-next psql $DATABASE_URL

# 检查表是否存在
\dt invite*

# 检查 user 表字段
\d user

# 退出
\q
```

**预期结果：**
- 应该看到 `invite_rebate_log` 和 `invite_stats` 表
- user 表应该包含 `invite_code` 和 `invited_by` 字段

## 注意事项

1. **备份数据库** - 在生产环境执行迁移前，务必备份数据库
2. **低流量时段** - 建议在系统负载较低时执行迁移
3. **监控日志** - 执行迁移时监控容器日志：`docker logs -f open-webui-next`
4. **测试环境** - 建议先在测试环境验证迁移
5. **回滚准备** - 准备好回滚方案以防万一

## Docker 自动迁移配置

确保您的 Dockerfile 或启动脚本中包含以下内容：

```dockerfile
# Dockerfile 示例
CMD ["sh", "-c", "cd /app/backend && alembic upgrade head && uvicorn open_webui.main:app --host 0.0.0.0 --port 8080"]
```

或在 docker-compose.yml 中：

```yaml
services:
  open-webui-next:
    command: sh -c "cd /app/backend && alembic upgrade head && uvicorn open_webui.main:app --host 0.0.0.0 --port 8080"
```

## 获取帮助

如果迁移过程中遇到问题：

1. 查看容器日志：`docker logs open-webui-next`
2. 检查数据库连接：确保 DATABASE_URL 环境变量正确
3. 验证迁移文件：确保所有迁移文件都在 `backend/open_webui/migrations/versions/` 目录中

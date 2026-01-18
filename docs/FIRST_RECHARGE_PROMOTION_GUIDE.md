# 首充福利感知方案 - 集成指南

## 概述

本方案通过多触点设计，在用户旅程的关键节点展示首充福利，最大化用户感知和转化率。

## 已创建的组件

### 1. FirstRechargeBonusModal.svelte
**位置**: `src/lib/components/billing/FirstRechargeBonusModal.svelte`

**用途**: 新用户首次登录时的欢迎弹窗

**集成方式**:
```svelte
<!-- 在 src/routes/(app)/+layout.svelte 中 -->
<script>
  import FirstRechargeBonusModal from '$lib/components/billing/FirstRechargeBonusModal.svelte';
  import { onMount } from 'svelte';

  let showFirstRechargeModal = false;

  onMount(() => {
    // 检查是否是新用户且未充值
    const hasShown = localStorage.getItem('firstRechargeBonusModalShown');
    if (!hasShown) {
      showFirstRechargeModal = true;
    }
  });
</script>

<FirstRechargeBonusModal bind:show={showFirstRechargeModal} />
```

**特点**:
- 🎁 醒目的礼物图标
- 💰 实时显示奖励比例和最高金额
- ✓ 三大特点列表
- 🔘 "立即充值" 和 "稍后再说" 按钮

---

### 2. LowBalanceAlert.svelte (已增强)
**位置**: `src/lib/components/billing/LowBalanceAlert.svelte`

**用途**: 余额不足时显示提醒，并突出首充奖励

**已有集成**: 该组件已在多个页面使用，无需额外集成

**新增功能**:
- 🎁 首充用户会看到 "首充送 XX% 奖励" 的高亮标签
- 🔘 "立即充值领取奖励" 按钮（仅首充用户可见）
- ✨ 脉冲动画效果

---

### 3. FirstRechargeBadge.svelte
**位置**: `src/lib/components/billing/FirstRechargeBadge.svelte`

**用途**: 导航栏"充值"菜单项的红点/NEW标签

**集成方式**:
```svelte
<!-- 在导航栏的充值链接旁边 -->
<script>
  import FirstRechargeBadge from '$lib/components/billing/FirstRechargeBadge.svelte';
</script>

<a href="/billing" class="nav-link">
  充值
  <FirstRechargeBadge />
</a>
```

**特点**:
- 🔴 红色 NEW 徽章
- ⚪ 脉冲动画的白点
- 📍 自动检测首充资格

---

### 4. FirstRechargeInlineTip.svelte
**位置**: `src/lib/components/billing/FirstRechargeInlineTip.svelte`

**用途**: 聊天界面底部的温和提示

**集成方式**:
```svelte
<!-- 在聊天页面 src/routes/(app)/c/[id]/+page.svelte -->
<script>
  import FirstRechargeInlineTip from '$lib/components/billing/FirstRechargeInlineTip.svelte';

  let messageCount = 0; // 跟踪用户发送的消息数

  // 每次用户发送消息时增加计数
  function handleSendMessage() {
    messageCount++;
    // ... 发送消息逻辑
  }
</script>

<FirstRechargeInlineTip {messageCount} showAfterMessages={5} />
```

**特点**:
- 💡 非侵入式的底部提示
- 📊 基于使用次数触发（默认5条消息后）
- 🚫 可关闭，关闭后不再显示
- 📱 响应式设计，移动端友好

---

### 5. RechargeCard.svelte (已优化)
**位置**: `src/lib/components/billing/RechargeCard.svelte`

**用途**: 充值页面的首充横幅

**已有功能**: 该组件已经有首充横幅，建议进一步优化：
- 添加 "NEW" 标签
- 添加背景装饰
- 增强动画效果

---

## 完整用户旅程

### 场景 1: 新用户首次登录
1. **触发**: 用户首次注册/登录
2. **展示**: `FirstRechargeBonusModal` 弹窗
3. **行动**: 用户点击"立即充值"跳转到充值页面

### 场景 2: 用户浏览应用
1. **触发**: 用户在应用中浏览
2. **展示**: 导航栏显示 `FirstRechargeBadge` 红点
3. **行动**: 吸引用户点击充值菜单

### 场景 3: 用户使用功能
1. **触发**: 用户发送5条消息后
2. **展示**: `FirstRechargeInlineTip` 底部提示
3. **行动**: 用户点击"去充值"

### 场景 4: 余额不足
1. **触发**: 用户余额低于阈值
2. **展示**: `LowBalanceAlert` 顶部横幅（含首充奖励信息）
3. **行动**: 用户点击"立即充值领取奖励"

### 场景 5: 主动充值
1. **触发**: 用户访问充值页面
2. **展示**: `RechargeCard` 首充横幅
3. **行动**: 用户选择金额并充值

---

## 配置选项

### 后端配置
首充奖励配置在后端管理面板：
- `bonus_rate`: 奖励比例（如 0.2 表示 20%）
- `max_bonus_amount`: 最高奖励金额（单位：毫，10000毫 = 1元）
- `enabled`: 是否启用首充奖励

### 前端配置
可调整的参数：
- `showAfterMessages`: 聊天提示触发的消息数（默认5）
- 弹窗显示逻辑（localStorage 键名）
- 动画效果和样式

---

## 数据流

```
用户登录
  ↓
检查首充资格 (checkFirstRechargeBonusEligibility)
  ↓
获取首充配置 (getFirstRechargeBonusConfig)
  ↓
根据资格显示相应组件
  ↓
用户充值
  ↓
首充标记更新
  ↓
隐藏所有首充提示
```

---

## API 依赖

所有组件依赖以下 API：
- `getFirstRechargeBonusConfig(token)`: 获取首充配置
- `checkFirstRechargeBonusEligibility(token)`: 检查用户是否符合首充资格

这些 API 已在 `src/lib/apis/first-recharge-bonus/index.ts` 中定义。

---

## 样式特点

### 设计语言
- **颜色**: 金色/橙色渐变（#fbbf24 → #f59e0b）
- **动画**: 脉冲、弹跳、滑入效果
- **图标**: 礼物 🎁、灯泡 💡、红点 🔴
- **字体**: 粗体强调关键数字

### 响应式设计
- 桌面端: 完整布局
- 移动端: 自适应布局，圆角按钮

---

## 性能优化

1. **懒加载**: 组件仅在需要时加载
2. **缓存**: localStorage 缓存用户关闭状态
3. **并行请求**: 使用 `Promise.all` 同时获取配置和资格
4. **条件渲染**: 仅在符合条件时渲染组件

---

## 测试建议

### 测试场景
1. ✅ 新用户首次登录 → 应显示欢迎弹窗
2. ✅ 已充值用户 → 不应显示任何首充提示
3. ✅ 余额不足 → 应显示增强版提醒
4. ✅ 发送5条消息 → 应显示聊天提示
5. ✅ 访问充值页面 → 应显示首充横幅

### 测试用户状态
- 新用户（未充值）
- 老用户（已充值）
- 余额充足用户
- 余额不足用户

---

## 后续优化建议

1. **A/B 测试**: 测试不同触发时机和文案
2. **数据埋点**: 跟踪各触点的点击率和转化率
3. **个性化**: 根据用户行为调整展示频率
4. **倒计时**: 添加限时优惠倒计时
5. **社交证明**: 显示"已有 XXX 人参与"

---

## 注意事项

⚠️ **重要提醒**:
1. 确保后端首充奖励系统已启用
2. 测试时注意清除 localStorage 缓存
3. 移动端测试支付宝 H5 支付流程
4. 确保所有文案已添加到 i18n 翻译文件

---

## 联系与支持

如有问题，请检查：
1. 后端 API 是否正常响应
2. 用户 token 是否有效
3. 浏览器控制台是否有错误
4. localStorage 是否被清除

---

**设计完成时间**: 2026-01-18
**版本**: v1.0

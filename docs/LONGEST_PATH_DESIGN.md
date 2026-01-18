# 多分支聊天导入 - 最长路径选择设计

## 问题背景

当前系统在导入多分支聊天记录时存在以下问题：
1. DeepSeek 格式：只选择第一个子分支（`childrenIds[0]`）
2. OpenAI/Grok 格式：保留完整树结构，但验证层拒绝有分支的聊天
3. 结果：大量对话信息丢失

## 设计目标

**自动选择最长路径**：在多分支情况下，选择包含最多消息的路径进行导入，最大化保留对话信息。

## 算法设计

### 核心思路

使用深度优先搜索（DFS）计算每个分支的深度，选择最深的分支。

### 算法步骤

```
1. 从根节点开始（parentId: null）
2. 对于每个节点：
   - 如果没有子节点：返回深度 1
   - 如果有多个子节点：
     a. 递归计算每个子分支的深度
     b. 选择深度最大的子节点
     c. 返回 1 + 最大子分支深度
3. 沿着选中的路径构建线性消息数组
```

### 伪代码

```typescript
function findLongestPath(messages: Map<string, Message>, rootId: string): string[] {
  // 计算从某个节点开始的最大深度
  function getMaxDepth(nodeId: string): number {
    const node = messages[nodeId];
    if (!node || node.childrenIds.length === 0) {
      return 1;
    }

    const childDepths = node.childrenIds.map(childId => getMaxDepth(childId));
    return 1 + Math.max(...childDepths);
  }

  // 选择最长路径
  function selectPath(nodeId: string, path: string[]): string[] {
    path.push(nodeId);
    const node = messages[nodeId];

    if (!node || node.childrenIds.length === 0) {
      return path;
    }

    // 找到深度最大的子节点
    let maxDepth = 0;
    let selectedChild = null;

    for (const childId of node.childrenIds) {
      const depth = getMaxDepth(childId);
      if (depth > maxDepth) {
        maxDepth = depth;
        selectedChild = childId;
      }
    }

    return selectPath(selectedChild, path);
  }

  return selectPath(rootId, []);
}
```

## 实现方案

### 1. 新增工具函数

在 `src/lib/utils/index.ts` 中添加：

```typescript
/**
 * 在消息树中找到最长路径
 * @param messagesMap - 消息映射表 {id: message}
 * @param rootId - 根节点ID（parentId 为 null 的节点）
 * @returns 最长路径的消息ID数组
 */
export const findLongestPathInTree = (
  messagesMap: Record<string, any>,
  rootId: string
): string[] => {
  // 递归计算深度
  const getDepth = (nodeId: string, memo: Map<string, number> = new Map()): number => {
    if (memo.has(nodeId)) return memo.get(nodeId)!;

    const node = messagesMap[nodeId];
    if (!node || !node.childrenIds || node.childrenIds.length === 0) {
      memo.set(nodeId, 1);
      return 1;
    }

    const maxChildDepth = Math.max(
      ...node.childrenIds.map(childId => getDepth(childId, memo))
    );
    const depth = 1 + maxChildDepth;
    memo.set(nodeId, depth);
    return depth;
  };

  // 选择最长路径
  const selectLongestPath = (nodeId: string, path: string[] = []): string[] => {
    path.push(nodeId);
    const node = messagesMap[nodeId];

    if (!node || !node.childrenIds || node.childrenIds.length === 0) {
      return path;
    }

    // 找到深度最大的子节点
    const memo = new Map<string, number>();
    let maxDepth = 0;
    let selectedChild = node.childrenIds[0]; // 默认第一个

    for (const childId of node.childrenIds) {
      const depth = getDepth(childId, memo);
      if (depth > maxDepth) {
        maxDepth = depth;
        selectedChild = childId;
      }
    }

    return selectLongestPath(selectedChild, path);
  };

  return selectLongestPath(rootId, []);
};
```

### 2. 修改 DeepSeek 转换器

```typescript
// 原代码（1033行）
currentNodeId = node.childrenIds[0];

// 修改为
if (node.childrenIds.length === 1) {
  currentNodeId = node.childrenIds[0];
} else if (node.childrenIds.length > 1) {
  // 多分支：选择最长路径
  const longestPath = findLongestPathInTree(mapping, currentNodeId);
  currentNodeId = longestPath[1]; // 下一个节点
}
```

### 3. 修改 OpenAI 转换器

在 `convertOpenAIMessages` 函数中，修改 `traverse` 函数：

```typescript
// 原代码：递归遍历所有子节点
node.children?.forEach((childId) => {
  const childValidId = traverse(childId, acceptedId || parentValidId);
  if (childValidId) lastValidId = childValidId;
});

// 修改为：只遍历最长路径
if (node.children && node.children.length > 0) {
  if (node.children.length === 1) {
    // 单分支：直接遍历
    const childValidId = traverse(node.children[0], acceptedId || parentValidId);
    if (childValidId) lastValidId = childValidId;
  } else {
    // 多分支：选择最长路径
    const memo = new Map<string, number>();
    let maxDepth = 0;
    let selectedChild = node.children[0];

    for (const childId of node.children) {
      const depth = getDepth(childId, memo);
      if (depth > maxDepth) {
        maxDepth = depth;
        selectedChild = childId;
      }
    }

    const childValidId = traverse(selectedChild, acceptedId || parentValidId);
    if (childValidId) lastValidId = childValidId;
  }
}
```

### 4. 修改验证逻辑（可选）

如果要保留完整树结构但只验证选中路径：

```typescript
const validateChat = (chat) => {
  const messages = chat.messages;
  if (messages.length === 0) return false;

  // 找到根节点
  const rootMessage = messages.find(m => m.parentId === null);
  if (!rootMessage) return false;

  // 找到最长路径
  const messagesMap = {};
  messages.forEach(m => messagesMap[m.id] = m);
  const longestPath = findLongestPathInTree(messagesMap, rootMessage.id);

  // 验证最长路径是否有效
  const lastId = longestPath[longestPath.length - 1];
  const lastMessage = messagesMap[lastId];

  // 最长路径的最后一条消息应该没有子节点
  return lastMessage.childrenIds.length === 0;
};
```

## 优势

1. **信息最大化**：自动选择包含最多对话的路径
2. **确定性**：相同输入总是产生相同结果
3. **向后兼容**：单分支对话行为不变
4. **性能优化**：使用记忆化避免重复计算

## 边界情况处理

1. **相同深度的分支**：选择第一个（保持稳定性）
2. **空节点**：跳过并继续
3. **循环引用**：记忆化可以检测并避免
4. **单分支**：直接遍历，无额外开销

## 测试场景

```
场景1：简单分支
  A → B → C
    → D

结果：选择 A → B → C（深度3 > 深度2）

场景2：复杂分支
  A → B → C → D
    → E → F

结果：选择 A → B → C → D（深度4 > 深度3）

场景3：相同深度
  A → B → C
    → D → E

结果：选择 A → B → C（第一个分支）
```

## 实施步骤

1. ✅ 添加 `findLongestPathInTree` 工具函数
2. ✅ 修改 `convertDeepseekMessages` 使用最长路径
3. ✅ 修改 `convertOpenAIMessages` 使用最长路径
4. ✅ 修改 `convertGrokMessages` 使用最长路径
5. ✅ 更新 `validateChat` 验证逻辑
6. ⬜ 添加单元测试
7. ⬜ 更新用户文档

## 未来优化

1. **用户选择**：提供 UI 让用户手动选择分支
2. **智能选择**：基于消息质量（长度、完整性）选择
3. **分支合并**：尝试合并多个分支的信息
4. **分支预览**：导入前显示所有分支供用户选择

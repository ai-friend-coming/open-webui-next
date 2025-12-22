/**
 * 消息信息量评分模块（前端版本）
 *
 * 提供对聊天消息进行信息量评分的工具函数，用于从导入的聊天记录中筛选高价值消息。
 *
 * 评分算法：
 * - 问题长度得分：25%权重
 * - 回复长度得分：25%权重
 * - 压缩比得分：50%权重（zlib压缩，压缩比越低信息密度越高）
 */

import pako from 'pako';

/**
 * 从消息对象中提取纯文本内容（处理多模态content）
 *
 * @param message - 消息对象，content可能是string或array（多模态消息）
 * @returns 纯文本内容
 */
export function extractTextContent(message: any): string {
	const content = message?.content || '';

	// 处理多模态消息（如图片+文本）
	if (Array.isArray(content)) {
		for (const item of content) {
			if (item?.type === 'text') {
				return item.text || '';
			}
		}
		// 没有找到文本内容
		return '';
	}

	// 处理普通字符串内容
	return typeof content === 'string' ? content : String(content || '');
}

/**
 * 计算文本的压缩比得分（1 - compression_ratio）
 *
 * 使用zlib压缩算法评估文本的信息熵。压缩比越低表示信息密度越高（高熵文本难压缩）。
 *
 * @param text - 待评估文本
 * @returns 压缩比得分 (0-1区间，1表示完全不可压缩，0表示完全可压缩)
 */
export function calculateCompressionScore(text: string): number {
	if (!text) {
		return 0.0;
	}

	try {
		const textBytes = new TextEncoder().encode(text);
		const compressed = pako.deflate(textBytes);
		const compressionRatio = compressed.length / textBytes.length;

		// 转换为得分：压缩比0.3 → 得分0.7（压缩比低 → 得分高）
		return 1.0 - compressionRatio;
	} catch (e) {
		console.warn('Failed to calculate compression score:', e);
		return 0.0;
	}
}

/**
 * Min-Max标准化，防止除零错误
 */
function normalize(values: number[]): number[] {
	if (values.length === 0) {
		return [];
	}

	const minVal = Math.min(...values);
	const maxVal = Math.max(...values);

	if (maxVal === minVal) {
		// 所有值相同时，统一赋值0.5
		return values.map(() => 0.5);
	}

	return values.map((v) => (v - minVal) / (maxVal - minVal));
}

/**
 * 评分结果接口
 */
export interface ScoredMessage {
	message: any; // 原始用户消息对象
	score: number; // 信息量得分（0-1）
	assistantReply: any | null; // 配对的助手回复（可能为null）
}

/**
 * 从聊天历史中选出信息量Top N的用户消息
 *
 * 算法流程：
 * 1. 遍历所有用户消息
 * 2. 为每条用户消息配对助手回复（通过parentId索引）
 * 3. 计算三维得分：问题长度、回复长度、压缩比
 * 4. 归一化各维度（Min-Max标准化到[0,1]）
 * 5. 加权求和：0.25 + 0.25 + 0.50
 * 6. 降序排序并返回Top N
 *
 * @param chat - 完整的聊天对象 {history: {messages: {...}}, title: "..."}
 * @param topN - 返回前N条消息（默认20）
 * @returns 按信息量得分降序排列的消息列表
 */
export function selectTopInformativeMessages(chat: any, topN: number = 20): ScoredMessage[] {
	const messagesMap = chat?.history?.messages || {};
	if (Object.keys(messagesMap).length === 0) {
		console.warn('No messages found in chat history');
		return [];
	}

	// 1. 构建parent_id索引（优化配对查找性能 O(N²) → O(N)）
	const parentMap: Record<string, any[]> = {};
	for (const [msgId, msg] of Object.entries(messagesMap)) {
		const parentId = (msg as any)?.parentId;
		if (parentId) {
			if (!parentMap[parentId]) {
				parentMap[parentId] = [];
			}
			parentMap[parentId].push(msg);
		}
	}

	// 2. 筛选所有用户消息并配对助手回复
	const userMessages: { message: any; assistantReply: any | null }[] = [];
	for (const [msgId, msg] of Object.entries(messagesMap)) {
		const msgObj = msg as any;
		if (msgObj?.role !== 'user') {
			continue;
		}

		// 查找子节点中的第一个assistant回复
		const children = parentMap[msgId] || [];
		const assistantMsg = children.find((m) => m?.role === 'assistant') || null;

		userMessages.push({
			message: msgObj,
			assistantReply: assistantMsg
		});
	}

	if (userMessages.length === 0) {
		console.info('No user messages found in chat');
		return [];
	}

	// 3. 计算原始指标
	interface Metric {
		item: { message: any; assistantReply: any | null };
		questionLen: number;
		replyLen: number;
		compressionScore: number;
	}

	const metrics: Metric[] = userMessages.map((item) => {
		const userText = extractTextContent(item.message);
		const assistantText = item.assistantReply ? extractTextContent(item.assistantReply) : '';

		return {
			item,
			questionLen: userText.length,
			replyLen: assistantText.length,
			compressionScore: calculateCompressionScore(userText)
		};
	});

	// 4. 归一化处理（Min-Max标准化到[0,1]）
	const qLens = metrics.map((m) => m.questionLen);
	const rLens = metrics.map((m) => m.replyLen);
	const cScores = metrics.map((m) => m.compressionScore);

	const normQ = normalize(qLens);
	const normR = normalize(rLens);
	const normC = normalize(cScores);

	// 5. 加权求和（问题长度25% + 回复长度25% + 压缩比50%）
	const scoredMessages: ScoredMessage[] = metrics.map((m, i) => {
		const totalScore = normQ[i] * 0.25 + normR[i] * 0.25 + normC[i] * 0.5;

		return {
			message: m.item.message,
			score: totalScore,
			assistantReply: m.item.assistantReply
		};
	});

	// 6. 排序并返回Top N
	scoredMessages.sort((a, b) => b.score - a.score);

	const actualTopN = Math.min(topN, scoredMessages.length);
	console.info(
		`Selected top ${actualTopN} informative messages out of ${scoredMessages.length} total user messages`
	);

	return scoredMessages.slice(0, actualTopN);
}

/**
 * 格式化Top消息为Mem0所需格式
 *
 * @param scoredMessages - 评分后的消息列表
 * @returns Mem0格式的消息列表 [{role: "user", content: "..."}]
 */
export function formatMessagesForMem0(scoredMessages: ScoredMessage[]): Array<{
	role: string;
	content: string;
}> {
	const messages = [];

	for (const item of scoredMessages) {
		const content = extractTextContent(item.message);
		if (content) {
			// 仅添加非空消息
			messages.push({
				role: 'user',
				content
			});
		}
	}

	return messages;
}

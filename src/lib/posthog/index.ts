import posthog from 'posthog-js';

export const initPosthog = () => {
	if (typeof window === 'undefined') {
		return;
	}

	// phc_Abmjxrycc5WX5tnegaHmQx5COrSTFmM72VmyDVv4xCa // 服务器 key
	posthog.init('phc_vftTp8xZG24u0OSnwvD0hbJO8ngB51JVT3ZWxse0lsL', {
		api_host: 'https://us.i.posthog.com',
		defaults: '2025-11-30',
		person_profiles: 'identified_only',
		autocapture: false, // 禁用点击、输入、表单提交等交互事件
		session_recording: {
			maskAllInputs: false,
			maskTextSelector: '.sensitive, .private, [data-sensitive="true"]'
		}
	});
};

export const signInTracking = (sessionUser: {
	id: string;
	email: string;
	name: string;
}) => {
	if (typeof window === 'undefined' || !sessionUser) {
		return;
	}

	posthog.identify(sessionUser.id, {
		email: sessionUser.email,
		name: sessionUser.name
	});
	posthog.capture('user_logged_in');
};

export const logOutTracking = (metadata: { reason?: string } = {}) => {
	if (typeof window === 'undefined') {
		return;
	}

	posthog.capture('user_logged_out', metadata);
	posthog.reset();
};

export const initTabTracking = () => {
	if (typeof window === 'undefined') {
		return null;
	}

	let isTabVisible = true;
	const tabId =
		sessionStorage.getItem('tab_id') || `${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

	sessionStorage.setItem('tab_id', tabId);

	posthog.register({
		tab_id: tabId,
		tab_opened_at: new Date().toISOString()
	});

	const heartbeatIntervalMs = 30 * 60 * 1000;

	// 心跳
	const heartbeatId = window.setInterval(() => {
		posthog.capture('tab_heartbeat', {
			page_url: window.location.href,
			visibility_state: document.visibilityState
		});
	}, heartbeatIntervalMs);

	// 🔑 1. 标签页可见性变化（切换标签页）
	const handleVisibilityChange = () => {
		const wasVisible = isTabVisible;
		isTabVisible = !document.hidden;

		if (document.visibilityState === 'hidden') {
			posthog.capture('tab_hidden', {
				page_url: window.location.href,
				time_visible: performance.now()
			});
		} else if (document.visibilityState === 'visible') {
			posthog.capture('tab_visible', {
				page_url: window.location.href,
				was_hidden_duration: wasVisible ? 0 : performance.now()
			});
		}
	};

	// 🔑 2. 监听窗口失去焦点（用户点击了其他应用）
	const handleBlur = () => {
		posthog.capture('window_blur', {
			page_url: window.location.href
		});
	};

	// 🔑 3. 监听窗口获得焦点
	const handleFocus = () => {
		posthog.capture('window_focus', {
			page_url: window.location.href
		});
	};

	// 🔑 4. 页面卸载（兼容性备选）
	const handleBeforeUnload = () => {
		posthog.capture('$pageleave', {
			$current_url: window.location.href
		});
	};

	// 🔑 5. 页面隐藏（关闭标签页或导航离开）
	const handlePageHide = (event: PageTransitionEvent) => {
		posthog.capture('page_hide', {
			page_url: window.location.href,
			persisted: event.persisted
		});
	};

	document.addEventListener('visibilitychange', handleVisibilityChange);
	window.addEventListener('blur', handleBlur);
	window.addEventListener('focus', handleFocus);
	window.addEventListener('beforeunload', handleBeforeUnload);
	window.addEventListener('pagehide', handlePageHide);

	return () => {
		window.clearInterval(heartbeatId);
		document.removeEventListener('visibilitychange', handleVisibilityChange);
		window.removeEventListener('blur', handleBlur);
		window.removeEventListener('focus', handleFocus);
		window.removeEventListener('beforeunload', handleBeforeUnload);
		window.removeEventListener('pagehide', handlePageHide);
	};
};

// =====================================================
// ==================== 导入聊天埋点 ====================
// =====================================================

/**
 * 导入聊天记录业务流程：
 * 用户可以从其他 AI 平台（DeepSeek、ChatGPT、Gemini、Grok、AI Studio、通义千问）导出聊天记录 JSON 文件，
 * 然后通过本平台的"导入聊天记录"功能将历史对话迁移到本平台。
 *
 * 完整流程：
 * 1. 用户点击侧边栏"导入聊天记录"按钮 → 打开 ImportChatsModal
 * 2. 用户上传 JSON 文件 → 系统解析文件内容
 * 3. 用户勾选要导入的聊天记录，选择是否导入记忆
 * 4. 用户点击"确认导入" → 系统逐条调用 API 导入聊天
 * 5. 用户可能中途关闭 Modal 放弃导入
 */

/**
 * 埋点1：import_chats_modal_open
 *
 * 【埋点时机】用户点击"导入聊天记录"按钮，ImportChatsModal 弹窗打开时
 * 【UI 操作】侧边栏底部 → 点击"导入聊天记录"按钮
 * 【业务环节】导入流程的起点，用户表达了导入意图
 * 【埋点数据】无
 */
export const trackImportChatsModalOpen = () => {
	if (typeof window === 'undefined') return;
	posthog.capture('import_chats_modal_open');
};

/**
 * 埋点2：import_chats_file_parsed
 *
 * 【埋点时机】用户上传的 JSON 文件解析成功后
 * 【UI 操作】ImportChatsModal → 拖拽或点击上传 JSON 文件 → 文件解析成功
 * 【业务环节】文件上传阶段完成，系统成功识别文件内容
 * 【埋点数据】
 *   - chatCount: number - 文件中包含的聊天记录数量
 */
export const trackImportChatsFileParsed = (chatCount: number) => {
	if (typeof window === 'undefined') return;
	posthog.capture('import_chats_file_parsed', { chatCount });
};

/**
 * 埋点3：import_chats_completed
 *
 * 【埋点时机】用户点击"确认导入"后，所有选中的聊天记录 API 调用完成时
 * 【UI 操作】ImportChatsModal → 勾选聊天记录 → 点击"确认导入"按钮 → 导入完成
 * 【业务环节】导入流程的终点（成功路径），用户完成了聊天数据迁移
 * 【埋点数据】
 *   - origin: string - 数据来源格式，用户从哪个平台导出的聊天数据 (deepseek/grok/aistudio/qwen/openai/webui)
 *   - totalCount: number - 成功导入的聊天总数
 *   - chats: Array - 每条聊天的详细信息数组：
 *       - chat_id: string - 导入后的聊天 ID
 *       - importMemory: boolean - 是否导入了记忆
 *       - messageCount: number - 消息数量
 *       - messageLengths: number[] - 每条消息的字符长度
 *       - latestMessageTime: string|null - 最新消息的时间 (ISO 8601)
 *       - createdAt: string|null - 聊天创建时间 (ISO 8601)
 *
 * @param origin 数据来源格式
 * @param importedChats 导入成功的聊天原始数据数组
 */
export const trackImportChatsCompleted = (
	origin: 'deepseek' | 'grok' | 'aistudio' | 'qwen' | 'openai' | 'webui',
	importedChats: Array<{
		importedChat: { id: string; created_at?: number };
		chat: any;
		importMemory: boolean;
	}>
) => {
	if (typeof window === 'undefined') return;
	if (importedChats.length === 0) return;

	// 解析每个 chat 的详细信息
	const chats = importedChats.map(({ importedChat, chat, importMemory }) => {
		const chatData = chat.chat || chat;
		const messages = chatData.messages || chatData.history?.messages || [];
		const messageArray = Array.isArray(messages) ? messages : Object.values(messages);

		// 计算每条消息的长度
		const messageLengths = messageArray.map((msg: any) => {
			const content = msg?.content || '';
			return typeof content === 'string' ? content.length : JSON.stringify(content).length;
		});

		// 获取最新消息时间
		let latestMessageTime: string | null = null;
		if (messageArray.length > 0) {
			const timestamps = messageArray
				.map((msg: any) => msg?.timestamp || msg?.created_at || msg?.updatedAt)
				.filter(Boolean);
			if (timestamps.length > 0) {
				const maxTs = Math.max(
					...timestamps.map((t: any) => (typeof t === 'number' ? t : new Date(t).getTime()))
				);
				latestMessageTime = new Date(maxTs).toISOString();
			}
		}

		return {
			chat_id: importedChat.id,
			importMemory,
			messageCount: messageArray.length,
			messageLengths,
			latestMessageTime,
			createdAt: importedChat.created_at
				? new Date(importedChat.created_at * 1000).toISOString()
				: null
		};
	});

	posthog.capture('import_chats_completed', {
		origin,
		totalCount: chats.length,
		chats
	});
};

/**
 * 埋点4：import_chats_modal_closed
 *
 * 【埋点时机】用户关闭 ImportChatsModal 且未完成导入时
 * 【UI 操作】ImportChatsModal → 点击"取消"按钮 / 点击右上角 × / 点击遮罩层
 * 【业务环节】导入流程的终点（放弃路径），用户中途退出未完成导入
 * 【埋点数据】
 *   - stage: 'before_upload' | 'after_upload' - 退出阶段
 *       - 'before_upload': 用户未上传文件就关闭了弹窗
 *       - 'after_upload': 用户已上传文件但未点击确认导入就关闭了弹窗
 */
export const trackImportChatsModalClosed = (stage: 'before_upload' | 'after_upload') => {
	if (typeof window === 'undefined') return;
	posthog.capture('import_chats_modal_closed', { stage });
};

// =====================================================
// ==================== 调整记忆埋点 ====================
// =====================================================

/**
 * 调整记忆业务流程：
 * 用户可以在平台中管理"记忆"，这些记忆是用户主动提供给 LLM 的个人信息，
 * LLM 在对话时可以访问这些记忆，从而提供更个性化的回复。
 *
 * 完整流程：
 * 1. 用户点击侧边栏"Memory"按钮 → 进入 /memories 页面
 * 2. 用户可以添加新记忆 → 打开 AddMemoryModal → 输入内容 → 保存
 * 3. 用户可以编辑已有记忆 → 打开 EditMemoryModal → 修改内容 → 保存
 * 4. 用户可以删除已有记忆 → 点击删除按钮 → 记忆被删除
 */

/** 记忆对象类型（用于埋点函数参数） */
interface MemoryForTracking {
	id: string;
	content?: string;
}

/** 提取记忆内容长度的工具函数 */
const getContentLength = (content?: string): number => content?.length || 0;

/**
 * 埋点1：memory_page_open
 *
 * 【埋点时机】用户点击侧边栏"Memory"按钮，进入 /memories 页面时
 * 【UI 操作】侧边栏 → 点击 Memory 按钮（Sparkles 图标）
 * 【业务环节】记忆管理的入口，用户表达了管理记忆的意图
 * 【埋点数据】无
 */
export const trackMemoryPageOpen = () => {
	if (typeof window === 'undefined') return;
	posthog.capture('memory_page_open');
};

/**
 * 埋点2：memory_added
 *
 * 【埋点时机】用户在 AddMemoryModal 中点击"Add"按钮，API 调用成功后
 * 【UI 操作】/memories 页面 → 点击"Add Memory"按钮 → 填写内容 → 点击"Add"
 * 【业务环节】新增记忆成功，用户完成了一条新记忆的创建
 * 【埋点数据】
 *   - memory_id: string - 新增记忆的 ID
 *   - content_length: number - 记忆内容的字符数
 *
 * @param memory - API 返回的新增记忆对象
 */
export const trackMemoryAdded = (memory: MemoryForTracking) => {
	if (typeof window === 'undefined') return;
	posthog.capture('memory_added', {
		memory_id: memory.id,
		content_length: getContentLength(memory.content)
	});
};

/**
 * 埋点3：memory_deleted
 *
 * 【埋点时机】用户点击记忆卡片上的删除按钮，API 调用成功后
 * 【UI 操作】/memories 页面 → 悬停记忆卡片 → 点击删除按钮（垃圾桶图标）
 * 【业务环节】删除记忆成功，用户移除了一条不再需要的记忆
 * 【埋点数据】
 *   - memory_id: string - 被删除记忆的 ID
 *   - content_length: number - 被删除记忆的字符数
 *
 * @param memory - 被删除的记忆对象
 */
export const trackMemoryDeleted = (memory: MemoryForTracking) => {
	if (typeof window === 'undefined') return;
	posthog.capture('memory_deleted', {
		memory_id: memory.id,
		content_length: getContentLength(memory.content)
	});
};

/**
 * 埋点4：memory_edited
 *
 * 【埋点时机】用户在 EditMemoryModal 中点击"Update"按钮，API 调用成功后
 * 【UI 操作】/memories 页面 → 悬停记忆卡片 → 点击编辑按钮（铅笔图标） → 修改内容 → 点击"Update"
 * 【业务环节】编辑记忆成功，用户修改了一条已有记忆的内容
 * 【埋点数据】
 *   - memory_id: string - 被编辑记忆的 ID
 *   - content_length_before: number - 编辑前的字符数
 *   - content_length_after: number - 编辑后的字符数
 *
 * @param originalMemory - 编辑前的原始记忆对象
 * @param newContent - 编辑后的新内容字符串
 */
export const trackMemoryEdited = (originalMemory: MemoryForTracking, newContent: string) => {
	if (typeof window === 'undefined') return;
	posthog.capture('memory_edited', {
		memory_id: originalMemory.id,
		content_length_before: getContentLength(originalMemory.content),
		content_length_after: getContentLength(newContent)
	});
};


import posthog from 'posthog-js';

// =====================================================
// ============== PostHog 初始化与基础埋点 ==============
// =====================================================

/**
 * PostHog 基础追踪业务流程：
 * PostHog 是本平台的用户行为分析工具，用于收集用户行为数据以优化产品体验。
 * 基础追踪包括：SDK 初始化、用户身份识别（登录/登出）、标签页活跃状态监控。
 *
 * 初始化流程：
 * 1. 应用启动 → 调用 initPosthog() 初始化 SDK
 * 2. 用户登录 → 调用 signInTracking() 关联用户身份
 * 3. 页面加载 → 调用 initTabTracking() 开始监控标签页状态
 * 4. 用户登出 → 调用 logOutTracking() 重置用户身份
 */

/**
 * 初始化：initPosthog
 *
 * 【调用时机】应用启动时，在根布局组件 (+layout.svelte) 中调用
 * 【功能说明】初始化 PostHog JavaScript SDK，配置数据收集策略
 * 【配置说明】
 *   - api_host: PostHog 数据接收服务器地址（美国节点）
 *   - person_profiles: 'identified_only' - 仅为已登录用户创建用户档案
 *   - autocapture: false - 禁用自动捕获（点击、输入等），只收集手动埋点
 *   - session_recording: 会话录制配置，支持敏感信息遮罩
 */
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

/**
 * 埋点：user_logged_in
 *
 * 【埋点时机】用户登录成功后，获取到用户信息时调用
 * 【UI 操作】登录页面 → 输入凭证 → 点击登录 → 登录成功
 * 【业务环节】用户身份识别，将后续所有事件与该用户关联
 * 【功能说明】
 *   - posthog.identify(): 将匿名用户转为已识别用户，关联用户 ID 和属性
 *   - posthog.capture('user_logged_in'): 记录登录事件
 * 【埋点数据】
 *   - 用户属性 (通过 identify 设置):
 *       - email: string - 用户邮箱
 *       - name: string - 用户名称
 *
 * @param sessionUser - 登录成功后的用户会话信息
 */
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

/**
 * 埋点：user_logged_out
 *
 * 【埋点时机】用户点击登出按钮，执行登出操作时调用
 * 【UI 操作】用户菜单 → 点击"登出"按钮
 * 【业务环节】用户会话结束，清除用户身份关联
 * 【功能说明】
 *   - posthog.capture('user_logged_out'): 记录登出事件
 *   - posthog.reset(): 重置用户身份，后续事件将作为匿名用户记录
 * 【埋点数据】
 *   - reason?: string - 可选，登出原因（如 'manual'、'session_expired' 等）
 *
 * @param metadata - 登出元数据，包含可选的登出原因
 */
export const logOutTracking = (metadata: { reason?: string } = {}) => {
	if (typeof window === 'undefined') {
		return;
	}

	posthog.capture('user_logged_out', metadata);
	posthog.reset();
};

/**
 * 标签页追踪初始化：initTabTracking
 *
 * 【调用时机】用户登录成功后，在根布局组件中初始化
 * 【功能说明】监控用户标签页的活跃状态，用于分析用户使用模式和会话时长
 * 【业务环节】用户活跃度监控，帮助理解用户如何与应用交互
 *
 * 【追踪的事件】
 *   1. tab_heartbeat - 心跳事件，每 30 分钟发送一次
 *      - page_url: string - 当前页面 URL
 *      - visibility_state: string - 标签页可见状态
 *
 *   2. tab_hidden - 标签页被隐藏（用户切换到其他标签页）
 *      - page_url: string - 当前页面 URL
 *      - time_visible: number - 标签页可见的持续时间（毫秒）
 *
 *   3. tab_visible - 标签页变为可见（用户切换回本标签页）
 *      - page_url: string - 当前页面 URL
 *      - was_hidden_duration: number - 标签页隐藏的持续时间（毫秒）
 *
 *   4. window_blur - 窗口失去焦点（用户点击了其他应用）
 *      - page_url: string - 当前页面 URL
 *
 *   5. window_focus - 窗口获得焦点（用户回到浏览器）
 *      - page_url: string - 当前页面 URL
 *
 *   6. $pageleave - 页面卸载（用户关闭标签页或导航离开）
 *      - $current_url: string - 当前页面 URL
 *
 *   7. page_hide - 页面隐藏（关闭标签页或导航离开的补充事件）
 *      - page_url: string - 当前页面 URL
 *      - persisted: boolean - 页面是否被缓存（bfcache）
 *
 * 【全局属性】通过 posthog.register() 注册，附加到所有后续事件：
 *   - tab_id: string - 唯一标签页标识符，用于区分同一用户的多个标签页
 *   - tab_opened_at: string - 标签页打开时间 (ISO 8601)
 *
 * @returns 清理函数，用于移除所有事件监听器和定时器；如果在服务端调用则返回 null
 */
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
 *       - modelUsage: Record<string, number> - 模型使用次数统计
 *           示例: {"gpt-4o": 23, "gpt-5.1": 10} 表示该 chat 中 gpt-4o 回复了 23 次，gpt-5.1 回复了 10 次
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

		// 统计模型使用次数（仅统计 assistant 角色的消息）
		const modelUsage: Record<string, number> = {};
		messageArray.forEach((msg: any) => {
			// 只统计 assistant/model 角色的回复
			const role = msg?.role || '';
			if (role !== 'assistant' && role !== 'model') return;

			// 尝试从多个可能的字段获取模型名称
			const model =
				msg?.model ||
				msg?.metadata?.model_slug ||
				(Array.isArray(msg?.models) && msg.models.length > 0 ? msg.models[0] : null);

			if (model && typeof model === 'string') {
				modelUsage[model] = (modelUsage[model] || 0) + 1;
			}
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
				: null,
			modelUsage
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

// =====================================================
// ==================== 进入聊天窗埋点 ====================
// =====================================================

/**
 * 进入聊天窗业务流程：
 * 用户通过侧边栏与聊天系统交互，主要有两种方式：
 * 1. 开始新对话 - 点击"新对话"按钮、Logo 或标题，跳转到空白聊天界面
 * 2. 进入已有聊天 - 点击侧边栏中的某个聊天项，加载历史消息
 *
 * 完整流程（进入已有聊天）：
 * 1. 用户点击侧边栏中的聊天项 → ChatItem 组件触发导航
 * 2. 路由跳转到 /c/{id} → Chat 组件接收 chatIdProp
 * 3. Chat 组件调用 loadChat() → 通过 getChatById API 获取完整数据
 * 4. 数据加载成功 → 触发埋点，记录聊天详情
 * 5. Messages 组件渲染历史消息
 */

/**
 * 埋点1：new_chat_started
 *
 * 【埋点时机】用户点击侧边栏元素开始新对话时
 * 【UI 操作】侧边栏 → 点击"新对话"按钮 / Logo 图标 / 标题文字
 * 【业务环节】新对话的起点，用户表达了开始新对话的意图
 * 【埋点数据】
 *   - source: string - 触发来源
 *       - 'new_chat_button': 点击"新对话"按钮
 *       - 'logo': 点击 Logo 图标
 *       - 'title': 点击标题文字
 *
 * @param source - 触发来源
 */
export const trackNewChatStarted = (source: 'new_chat_button' | 'logo' | 'title') => {
	if (typeof window === 'undefined') return;
	posthog.capture('new_chat_started', { source });
};

/**
 * 埋点2：chat_opened
 *
 * 【埋点时机】用户点击侧边栏聊天项，Chat 组件 loadChat 函数成功获取完整数据后
 * 【UI 操作】侧边栏 → 点击某个聊天项 → 聊天数据加载完成
 * 【业务环节】进入已有聊天，用户查看/继续历史对话
 * 【埋点数据】
 *   - chat_id: string - 聊天 ID
 *   - is_imported: boolean - 是否为用户导入的聊天记录 (chat.meta.loaded_by_user)
 *   - memory_enabled: boolean | undefined - 是否开启了记忆选项 (chat.chat.memory_enabled)
 *   - summary_time: number - summary 的次数 (chat.meta.summary_time)
 *   - message_count: number - 消息个数
 *   - message_lengths: number[] - 每条消息的内容字符数
 *   - model_usage: Record<string, { count: number; is_user_model: boolean }> - 模型使用统计（仅统计 assistant 消息）
 *       示例: {"gpt-4o": { count: 23, is_user_model: false }, "my-custom-model": { count: 10, is_user_model: true }}
 *       - count: 该模型回复的次数
 *       - is_user_model: 是否为用户私有 API 模型（true）还是系统内置模型（false）
 *   - created_at: string | null - 聊天创建时间 (ISO 8601)
 *   - latest_message_time: string | null - 最新消息时间 (ISO 8601)
 *
 * @param chat - 从 getChatById API 获取的完整聊天对象
 * @param history - 解析后的消息历史对象 { messages: { [id]: Message }, currentId: string }
 */
export const trackChatOpened = (chat: any, history: any) => {
	if (typeof window === 'undefined') return;
	if (!chat) return;

	// 解析数据（模块化，所有解析逻辑在此文件中）
	const parsedData = parseChatForTracking(chat, history);
	posthog.capture('chat_opened', parsedData);
};

/**
 * 解析 chat 数据用于埋点（内部工具函数）
 *
 * @param chat - 聊天对象
 * @param history - 消息历史对象
 * @returns 解析后的埋点数据
 */
const parseChatForTracking = (chat: any, history: any) => {
	const messages = history?.messages || {};
	const messageArray = Object.values(messages);

	// 计算每条消息的长度
	const messageLengths = messageArray.map((msg: any) => {
		const content = msg?.content || '';
		return typeof content === 'string' ? content.length : JSON.stringify(content).length;
	});

	// 统计模型使用次数（仅 assistant 消息），包含是否为用户私有模型
	const modelUsage: Record<string, { count: number; is_user_model: boolean }> = {};
	messageArray.forEach((msg: any) => {
		if (msg?.role !== 'assistant') return;
		const model = msg?.model;
		if (model && typeof model === 'string') {
			if (!modelUsage[model]) {
				modelUsage[model] = {
					count: 0,
					is_user_model: msg?.is_user_model ?? false
				};
			}
			modelUsage[model].count += 1;
		}
	});

	// 获取最新消息时间
	let latestMessageTime: string | null = null;
	if (messageArray.length > 0) {
		const timestamps = messageArray.map((msg: any) => msg?.timestamp).filter(Boolean);
		if (timestamps.length > 0) {
			const maxTs = Math.max(
				...timestamps.map((t: any) => (typeof t === 'number' ? t : new Date(t).getTime()))
			);
			// timestamp 是秒级时间戳，需要乘以 1000
			latestMessageTime = new Date(maxTs * 1000).toISOString();
		}
	}

	return {
		chat_id: chat.id,
		is_imported: chat.meta?.loaded_by_user ?? false,
		memory_enabled: chat.chat?.memory_enabled,
		summary_time: chat.meta?.summary_time ?? 0,
		message_count: messageArray.length,
		message_lengths: messageLengths,
		model_usage: modelUsage,
		created_at: chat.created_at ? new Date(chat.created_at * 1000).toISOString() : null,
		latest_message_time: latestMessageTime
	};
};

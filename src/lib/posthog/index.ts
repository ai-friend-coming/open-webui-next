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

	posthog.init('phc_Abmjxrycc5WX5tnegaHmQx5COrSTFmM72VmyDVv4xCa', {
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
 *       - phone: string - 用户手机号
 *       - name: string - 用户名称
 *       - role: string - 用户角色 (admin/user/pending)
 *
 * @param sessionUser - 登录成功后的用户会话信息
 */
export const signInTracking = (sessionUser: {
	id: string;
	email?: string;
	phone?: string;
	name: string;
	role?: string;
}) => {
	if (typeof window === 'undefined' || !sessionUser) {
		return;
	}

	posthog.identify(sessionUser.id, {
		...(sessionUser.email && { email: sessionUser.email }),
		...(sessionUser.phone && { phone: sessionUser.phone }),
		name: sessionUser.name,
		...(sessionUser.role && { role: sessionUser.role })
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
 * 【埋点数据】完整保存 chat 数据（脱敏处理）+ 消息数组 + 汇总统计
 *
 *   === 聊天元数据 ===
 *   - chat_id: string - 聊天 ID
 *   - title_length: number - 标题字符数（脱敏）
 *   - selected_models: string[] - 聊天选中的模型列表
 *   - params: object - 聊天参数设置
 *   - memory_enabled: boolean - 是否开启记忆
 *   - tags: string[] - 标签列表
 *   - files_count: number - 上传文件数量
 *   - created_at: string | null - 聊天创建时间 (ISO 8601)
 *   - updated_at: string | null - 最后更新时间 (ISO 8601)
 *   - meta: { summary_time: number, is_imported: boolean } - 元信息
 *
 *   === 消息数组（按时间顺序，脱敏处理）===
 *   - messages: Array<MessageData> - 每条消息的详细信息
 *
 *       [通用字段]
 *       - role: 'user' | 'assistant' - 消息角色
 *       - content_length: number - 内容字符数（脱敏）
 *       - timestamp: string | null - 消息时间 (ISO 8601)
 *
 *       [user 消息特有]
 *       - models?: string[] - 用户选择的模型列表
 *
 *       [assistant 消息特有]
 *       - model?: string - 使用的模型 ID
 *       - model_name?: string - 模型显示名称
 *       - model_idx?: number - 多模型对话索引
 *       - is_user_model?: boolean - 是否为用户私有 API 模型
 *       - done?: boolean - 是否完成生成
 *       - usage?: TokenUsage - token 使用详情 (原始 token 使用数据，直接保存)
 *           - prompt_tokens: number - 输入 tokens
 *           - completion_tokens: number - 输出 tokens
 *           - total_tokens: number - 总 tokens
 *           - cached_tokens: number - 缓存命中 tokens
 *           - reasoning_tokens: number - 推理 tokens（o1 等模型）
 *
 *   === 汇总统计 ===
 *   - stats: object - 统计汇总
 *       - message_count: number - 总消息数
 *       - user_message_count: number - 用户消息数
 *       - assistant_message_count: number - AI 回复数
 *       - conversation_turns: number - 对话轮数
 *       - total_content_length: number - 总内容字符数
 *       - latest_message_time: string | null - 最新消息时间
 *       - model_usage: Record<string, { count, is_user_model }> - 模型使用统计
 *       - total_token_usage: TokenUsage - token 使用汇总
 *
 * @param chat - 从 getChatById API 获取的完整聊天对象
 */
export const trackChatOpened = (chat: any) => {
	if (typeof window === 'undefined') return;
	if (!chat) return;

	const parsedData = parseChatForTracking(chat);
	posthog.capture('chat_opened', parsedData);
};

/** Token 使用详情类型 */
interface TokenUsage {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	cached_tokens: number;
	reasoning_tokens: number;
}

/** 消息埋点数据类型 */
interface MessageTrackingData {
	message_id: string;
	role: string;
	content_length: number;
	timestamp: string | null;
	models?: string[];
	model?: string;
	model_name?: string;
	model_idx?: number;
	is_user_model?: boolean;
	done?: boolean;
	usage?: any; // 直接保存原始 usage，兼容不同 API 格式
}

/**
 * 解析 chat 数据用于埋点
 * 忠实存储 chat 数据，对敏感内容进行脱敏处理
 *
 * @param chat - 聊天对象
 * @returns 解析后的埋点数据
 */
export const parseChatForTracking = (chat: any) => {
	const chatData = chat.chat || {};
	// 使用 chat.chat.messages 数组（已按时间顺序）
	const rawMessages: any[] = chatData.messages || [];

	// ==================== 解析每条消息 ====================
	const messages: MessageTrackingData[] = rawMessages.map((msg: any) => {
		const contentLength = getContentLength(msg?.content);
		const timestamp = msg?.timestamp
			? new Date(msg.timestamp * 1000).toISOString()
			: null;

		if (msg?.role === 'user') {
			return {
				message_id: msg?.id || '',
				role: 'user',
				content_length: contentLength,
				timestamp,
				...(msg?.models && { models: msg.models })
			};
		} else {
			// assistant 消息 - 直接保存原始 usage，不解析（兼容不同 API 格式）
			return {
				message_id: msg?.id || '',
				role: msg?.role || 'assistant',
				content_length: contentLength,
				timestamp,
				...(msg?.model && { model: msg.model }),
				...(msg?.modelName && { model_name: msg.modelName }),
				...(msg?.modelIdx !== undefined && { model_idx: msg.modelIdx }),
				...(msg?.is_user_model !== undefined && { is_user_model: msg.is_user_model }),
				...(msg?.done !== undefined && { done: msg.done }),
				...(msg?.usage && { usage: msg.usage })
			};
		}
	});

	// ==================== 汇总统计 ====================
	let userMessageCount = 0;
	let assistantMessageCount = 0;
	let totalContentLength = 0;
	let latestMessageTime: string | null = null;
	const modelUsage: Record<string, { count: number; is_user_model: boolean }> = {};
	const totalTokenUsage: TokenUsage = {
		prompt_tokens: 0,
		completion_tokens: 0,
		total_tokens: 0,
		cached_tokens: 0,
		reasoning_tokens: 0
	};

	messages.forEach((msg) => {
		// 角色计数
		if (msg.role === 'user') {
			userMessageCount++;
		} else if (msg.role === 'assistant') {
			assistantMessageCount++;

			// 模型使用统计
			if (msg.model) {
				if (!modelUsage[msg.model]) {
					modelUsage[msg.model] = {
						count: 0,
						is_user_model: msg.is_user_model ?? false
					};
				}
				modelUsage[msg.model].count++;
			}

			// Token 累加（兼容不同 API 的 usage 格式）
			if (msg.usage) {
				const usage = msg.usage;
				totalTokenUsage.prompt_tokens += usage.prompt_tokens || 0;
				totalTokenUsage.completion_tokens += usage.completion_tokens || 0;
				totalTokenUsage.total_tokens += usage.total_tokens || 0;
				totalTokenUsage.cached_tokens += usage.prompt_tokens_details?.cached_tokens || 0;
				totalTokenUsage.reasoning_tokens += usage.completion_tokens_details?.reasoning_tokens || 0;
			}
		}

		// 内容长度累加
		totalContentLength += msg.content_length;

		// 最新消息时间
		if (msg.timestamp) {
			if (!latestMessageTime || msg.timestamp > latestMessageTime) {
				latestMessageTime = msg.timestamp;
			}
		}
	});

	// ==================== 返回完整数据 ====================
	return {
		// 聊天元数据
		chat_id: chat.id,
		title_length: getContentLength(chat.title),
		selected_models: chatData.models || [],
		params: chatData.params || {},
		memory_enabled: chatData.memory_enabled ?? false,
		tags: chatData.tags || [],
		files_count: (chatData.files || []).length,
		created_at: chat.created_at ? new Date(chat.created_at * 1000).toISOString() : null,
		updated_at: chat.updated_at ? new Date(chat.updated_at * 1000).toISOString() : null,
		is_shared: chat.share_id !== null && chat.share_id !== undefined,
		is_archived: chat.archived ?? false,
		is_pinned: chat.pinned ?? false,
		has_folder: chat.folder_id !== null && chat.folder_id !== undefined,
		meta: {
			summary_time: chat.meta?.summary_time ?? 0,
			is_imported: chat.meta?.loaded_by_user ?? false
		},

		// 消息数组（按时间顺序）
		messages,

		// 汇总统计
		stats: {
			message_count: messages.length,
			user_message_count: userMessageCount,
			assistant_message_count: assistantMessageCount,
			conversation_turns: userMessageCount, // 对话轮数 = 用户消息数
			total_content_length: totalContentLength,
			latest_message_time: latestMessageTime,
			model_usage: modelUsage,
			total_token_usage: totalTokenUsage
		}
	};
};


// =====================================================
// ==================== 消息生命周期埋点 ====================
// =====================================================

// ==================== 原始数据接口（供业务层使用）====================

/** 请求发送时的业务数据 */
export interface MessageLifecycleSentData {
	isNewChat: boolean;
	chatId: string;
	userMessageId: string;
	messageLength: number;
	modelId: string;
	modelName: string;
	isUserModel: boolean;
	responseMessageId: string;
	chatContext: any;
	hasFiles: boolean;
	fileCount: number;
	selectedTools: string[];
	features: object;
}

/** 响应完成时的数据 */
export interface MessageLifecycleResponseData {
	responseLength: number;
	usage: any;
	hasSources: boolean;
	sourceCount: number;
	isArenaMode: boolean;
	selectedModelId?: string;
}

/** 错误数据 */
export interface MessageLifecycleErrorData {
	errorType: 'ws_error' | 'completion_error' | 'api_error' | 'http_error';
	error: any;
}

/** 请求生命周期的时间戳记录 */
export interface MessageLifecycleTimestamps {
	submitAt: number;
	sendRequestAt: number;
	httpResponseAt?: number;
	firstTokenAt?: number;
	endAt?: number;
}

/** 结果类型 */
export type MessageLifecycleOutcome = 'completed' | 'stopped' | 'error' | 'cancelled';

/** trackMessageLifecycle 的原始参数类型 */
export interface MessageLifecycleRawParams {
	outcome: MessageLifecycleOutcome;
	timestamps: MessageLifecycleTimestamps;
	sentData: MessageLifecycleSentData;
	responseData?: MessageLifecycleResponseData;
	errorData?: MessageLifecycleErrorData;
	partialResponseLength?: number;
}

/**
 * 消息生命周期埋点：message_lifecycle
 *
 * 【埋点时机】请求结束时（成功、停止、错误、取消）
 * 【业务环节】SendingRequestManagement 在以下时机调用：
 *   - completeRequest(): 成功完成
 *   - stopRequest(): 用户停止
 *   - failRequest(): 错误或取消
 *
 * 【埋点数据结构】
 *
 * === 结果类型 ===
 * - outcome: 'completed' | 'stopped' | 'error' | 'cancelled'
 *
 * === 时间戳 (ISO 8601 格式) ===
 * - timestamps.submit_at: 用户点击发送时间
 * - timestamps.send_request_at: 创建占位消息时间
 * - timestamps.http_response_at?: 收到 HTTP 响应时间
 * - timestamps.first_token_at?: 收到第一个 token 时间
 * - timestamps.end_at?: 结束时间
 *
 * === 耗时 (毫秒) ===
 * - durations.total?: 总耗时 (end - submit)
 * - durations.to_http_response?: 到 HTTP 响应耗时 (http_response - send_request)
 * - durations.to_first_token?: 到首 token 耗时 (first_token - send_request)
 * - durations.streaming?: 流式传输耗时 (end - first_token)
 *
 * === 发送数据 (sent) ===
 * - sent.is_new_chat: boolean - 是否新对话
 * - sent.chat_id: string - 聊天 ID
 * - sent.user_message_id: string - 用户消息 ID
 * - sent.message_length: number - 用户消息长度
 * - sent.model_id: string - 模型 ID
 * - sent.model_name: string - 模型名称
 * - sent.is_user_model: boolean - 是否用户私有模型
 * - sent.response_message_id: string - 响应消息 ID
 * - sent.has_files: boolean - 是否有附件
 * - sent.file_count: number - 附件数量
 * - sent.selected_tools: string[] - 选中的工具 ID 列表
 * - sent.features: object - 启用的功能开关
 *   - features.image_generation: boolean - 图像生成
 *   - features.code_interpreter: boolean - 代码解释器
 *   - features.web_search: boolean - 网页搜索
 *   - features.memory: boolean - 记忆功能
 * - sent.chat_context: object - 聊天上下文 (parseChatForTracking 返回)
 *   - chat_context.chat_id: string - 聊天 ID
 *   - chat_context.title_length: number - 标题长度
 *   - chat_context.selected_models: string[] - 选中的模型列表
 *   - chat_context.params: object - 模型参数
 *   - chat_context.memory_enabled: boolean - 是否启用记忆
 *   - chat_context.tags: string[] - 标签列表
 *   - chat_context.files_count: number - 附件数量
 *   - chat_context.created_at: string - 创建时间 (ISO 8601)
 *   - chat_context.updated_at: string - 更新时间 (ISO 8601)
 *   - chat_context.is_shared: boolean - 是否已分享
 *   - chat_context.is_archived: boolean - 是否已归档
 *   - chat_context.is_pinned: boolean - 是否已置顶
 *   - chat_context.has_folder: boolean - 是否在文件夹中
 *   - chat_context.meta: { summary_time: number, is_imported: boolean }
 *   - chat_context.messages: array - 消息历史
 *     - message_id, role, content_length, timestamp
 *     - models (user) / model, model_name, model_idx, is_user_model, done, usage (assistant)
 *   - chat_context.stats: object - 统计信息
 *     - message_count, user_message_count, assistant_message_count
 *     - conversation_turns, total_content_length, latest_message_time
 *     - model_usage: { [model_id]: { count, is_user_model } }
 *     - total_token_usage: { prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens }
 *
 * === 响应数据 (response) - 仅 outcome='completed' ===
 * - response.response_length: number - 响应内容长度
 * - response.has_sources: boolean - 是否有引用源
 * - response.source_count: number - 引用源数量
 * - response.is_arena_mode: boolean - 是否 Arena 模式
 * - response.selected_model_id?: string - Arena 模式下选中的模型 ID
 * - response.usage: object - Token 用量统计
 *   - usage.prompt_tokens: number - 输入 token 数
 *   - usage.completion_tokens: number - 输出 token 数
 *   - usage.total_tokens: number - 总 token 数
 *   - usage.prompt_tokens_details?: { cached_tokens, audio_tokens }
 *   - usage.completion_tokens_details?: { reasoning_tokens, audio_tokens, accepted_prediction_tokens, rejected_prediction_tokens }
 *
 * === 错误数据 (error) - 仅 outcome='error' | 'cancelled' ===
 * - error.error_type: 'ws_error' | 'completion_error' | 'api_error' | 'http_error'
 *   - ws_error: WebSocket chat:message:error 事件
 *   - completion_error: Completion 流中的 error 字段
 *   - api_error: HTTP 200 但响应体包含 error
 *   - http_error: HTTP 请求失败 (网络错误、超时等)
 * - error.error: any - 原始错误对象
 *
 * === 停止数据 (stopped) - 仅 outcome='stopped' ===
 * - stopped.partial_response_length: number - 停止时已收到的响应长度
 *
 * @param params - 原始埋点参数（业务层数据格式）
 */
export const trackMessageLifecycle = (params: MessageLifecycleRawParams) => {
	if (typeof window === 'undefined') return;

	const { outcome, timestamps, sentData, responseData, errorData, partialResponseLength } = params;

	// ========== 计算耗时 ==========
	const durations: Record<string, number | undefined> = {
		total: timestamps.endAt ? timestamps.endAt - timestamps.submitAt : undefined
	};

	if (timestamps.httpResponseAt) {
		durations.to_http_response = timestamps.httpResponseAt - timestamps.sendRequestAt;
	}

	if (timestamps.firstTokenAt) {
		durations.to_first_token = timestamps.firstTokenAt - timestamps.sendRequestAt;
	}

	if (timestamps.firstTokenAt && timestamps.endAt) {
		durations.streaming = timestamps.endAt - timestamps.firstTokenAt;
	}

	// ========== 构建埋点数据 ==========
	const eventData: any = {
		outcome,
		timestamps: {
			submit_at: new Date(timestamps.submitAt).toISOString(),
			send_request_at: new Date(timestamps.sendRequestAt).toISOString(),
			http_response_at: timestamps.httpResponseAt
				? new Date(timestamps.httpResponseAt).toISOString()
				: undefined,
			first_token_at: timestamps.firstTokenAt
				? new Date(timestamps.firstTokenAt).toISOString()
				: undefined,
			end_at: timestamps.endAt ? new Date(timestamps.endAt).toISOString() : undefined
		},
		durations,
		sent: {
			is_new_chat: sentData.isNewChat,
			chat_id: sentData.chatId,
			user_message_id: sentData.userMessageId,
			message_length: sentData.messageLength,
			model_id: sentData.modelId,
			model_name: sentData.modelName,
			is_user_model: sentData.isUserModel,
			response_message_id: sentData.responseMessageId,
			chat_context: sentData.chatContext,
			has_files: sentData.hasFiles,
			file_count: sentData.fileCount,
			selected_tools: sentData.selectedTools,
			features: sentData.features
		}
	};

	// ========== 根据 outcome 添加额外数据 ==========
	if (outcome === 'completed' && responseData) {
		eventData.response = {
			response_length: responseData.responseLength,
			usage: responseData.usage,
			has_sources: responseData.hasSources,
			source_count: responseData.sourceCount,
			is_arena_mode: responseData.isArenaMode,
			selected_model_id: responseData.selectedModelId
		};
	}

	if ((outcome === 'error' || outcome === 'cancelled') && errorData) {
		eventData.error = {
			error_type: errorData.errorType,
			error: errorData.error
		};
	}

	if (outcome === 'stopped') {
		eventData.stopped = {
			partial_response_length: partialResponseLength ?? 0
		};
	}

	// ========== 调试日志 ==========
	console.log(
		`%c📊 message_lifecycle [${outcome}]`,
		'color: #6366f1; font-weight: bold;',
		'\n',
		{
			'🎯 结果': outcome,
			'⏱️ 耗时': {
				'总耗时': durations.total ? `${durations.total}ms` : '-',
				'到HTTP响应': durations.to_http_response ? `${durations.to_http_response}ms` : '-',
				'到首Token': durations.to_first_token ? `${durations.to_first_token}ms` : '-',
				'流式传输': durations.streaming ? `${durations.streaming}ms` : '-'
			},
			'📤 发送': {
				'新对话': sentData.isNewChat,
				'聊天ID': sentData.chatId,
				'模型': `${sentData.modelName} (${sentData.modelId})`,
				'私有模型': sentData.isUserModel,
				'消息长度': sentData.messageLength,
				'附件': sentData.hasFiles ? `${sentData.fileCount}个文件` : '无'
			},
			...(outcome === 'completed' && responseData
				? {
						'📥 响应': {
							'响应长度': responseData.responseLength,
							'Token用量': responseData.usage,
							'引用源': responseData.hasSources ? `${responseData.sourceCount}个` : '无',
							'Arena模式': responseData.isArenaMode
						}
					}
				: {}),
			...(outcome === 'stopped'
				? { '⏹️ 停止时响应长度': partialResponseLength }
				: {}),
			...((outcome === 'error' || outcome === 'cancelled') && errorData
				? { '❌ 错误': { 类型: errorData.errorType, 详情: errorData.error } }
				: {}),
			'📋 完整数据': eventData
		}
	);

	posthog.capture('message_lifecycle', eventData);
};

// =====================================================
// ==================== 重新生成埋点 ====================
// =====================================================

/**
 * 重新生成消息业务流程：
 * 用户对已有 AI 响应不满意时，可以点击"重新生成"按钮要求 LLM 重新回复。
 * 与普通发送消息不同，重新生成会先删除旧的响应消息，然后调用 sendMessage 生成新响应。
 *
 * 完整数据流：
 * 1. 用户点击"重新生成"按钮 → regenerateResponse(message, suggestionPrompt?)
 * 2. 【埋点】trackMessageRegenerated() - 记录重新生成动作
 * 3. 删除旧的 assistant 响应消息
 * 4. 调用 sendMessage() → startRequest() → sendMessageSocket()
 * 5. WebSocket 流式响应 → completeRequest/failRequest/stopRequest → trackMessageLifecycle
 *
 * 重新生成选项：
 * - "Try Again" - 无提示词，直接重新生成
 * - "Add Details" - 追加建议提示词
 * - "More Concise" - 追加建议提示词
 * - 自定义输入 - 用户输入任意提示词
 */

/** 重新生成消息埋点参数类型 */
interface MessageRegeneratedParams {
	chatId: string;
	userMessageId: string;
	oldResponseMessageId: string;
	oldModelId: string;
	oldModelName: string;
	oldIsUserModel: boolean;
	oldResponseLength: number;
	suggestionPrompt: string | null;
	suggestionSource: 'preset' | 'custom' | null;
	isMultiModel: boolean;
	modelIdx: number | null;
}

/**
 * 埋点5：message_regenerated
 *
 * 【埋点时机】用户点击重新生成按钮，删除旧响应之前
 * 【UI 操作】点击重新生成按钮/菜单选项 → 触发 regenerateResponse()
 * 【业务环节】regenerateResponse() 开头 → 【埋点】→ 删除旧消息 → sendMessage()
 * 【埋点数据】
 *   === 关联标识 ===
 *   - chat_id: string - 聊天 ID
 *   - user_message_id: string - 关联的用户消息 ID
 *
 *   === 时间信息 ===
 *   - regenerated_at: string - 重新生成时间 (ISO 8601)
 *
 *   === 被删除的旧响应信息 ===
 *   - old_response: object - 旧响应详情
 *       - message_id: string - 旧响应消息 ID
 *       - model_id: string - 旧响应使用的模型
 *       - model_name: string - 旧响应模型名称
 *       - is_user_model: boolean - 是否为私有模型
 *       - response_length: number - 旧响应字符数
 *
 *   === 重新生成选项 ===
 *   - regenerate_type: 'simple_retry' | 'with_suggestion' - 重新生成类型
 *   - suggestion_prompt: string | null - 建议提示词
 *   - suggestion_source: 'preset' | 'custom' | null - 提示词来源
 *
 *   === 上下文信息 ===
 *   - is_multi_model: boolean - 是否为多模型模式
 *   - model_idx: number | null - 多模型时的模型索引
 *
 * @param params - 埋点参数
 */
export const trackMessageRegenerated = (params: MessageRegeneratedParams) => {
	if (typeof window === 'undefined') return;

	posthog.capture('message_regenerated', {
		// 关联标识
		chat_id: params.chatId,
		user_message_id: params.userMessageId,

		// 时间信息
		regenerated_at: new Date().toISOString(),

		// 被删除的旧响应信息
		old_response: {
			message_id: params.oldResponseMessageId,
			model_id: params.oldModelId,
			model_name: params.oldModelName,
			is_user_model: params.oldIsUserModel,
			response_length: params.oldResponseLength
		},

		// 重新生成选项
		regenerate_type: params.suggestionPrompt ? 'with_suggestion' : 'simple_retry',
		suggestion_prompt: params.suggestionPrompt,
		suggestion_source: params.suggestionSource,

		// 上下文信息
		is_multi_model: params.isMultiModel,
		model_idx: params.modelIdx
	});
};

// =====================================================
// ==================== 编辑消息埋点 ====================
// =====================================================

/**
 * 编辑用户消息业务流程：
 * 用户可以编辑已发送的用户消息，修改内容后重新发送。
 * 与"重新生成"类似，编辑后重新发送会删除原有的 assistant 响应，然后调用 sendMessage 生成新响应。
 *
 * 完整数据流：
 * 1. 用户点击用户消息的编辑按钮 → 进入编辑模式
 * 2. 用户修改消息内容/文件 → 点击发送按钮
 * 3. editMessage(messageId, { content, files }, submit=true)
 * 4. 【埋点】trackMessageEdited() - 记录编辑动作
 * 5. 删除所有子消息（assistant 响应）
 * 6. 调用 sendMessage() → startRequest() → sendMessageSocket()
 * 7. WebSocket 流式响应 → completeRequest/failRequest/stopRequest → trackMessageLifecycle
 *
 * 编辑消息 vs 重新生成的区别：
 * - 编辑消息：修改用户消息内容，删除所有响应后重新发送
 * - 重新生成：用户消息不变，只删除并重新生成 assistant 响应
 */

/** 被删除消息的埋点数据结构 */
export interface DeletedMessageTrackingData {
	messageId: string;
	role: string;
	modelId: string;
	modelName: string;
	isUserModel: boolean;
	contentLength: number;
}

/**
 * 递归收集消息子树中所有消息的埋点数据
 *
 * 用于编辑用户消息时，统计将要被剪枝删除的所有后续消息。
 * 这些消息包括 assistant 响应以及后续的 user/assistant 消息对。
 *
 * @param messages - history.messages 对象（消息 ID 到消息对象的映射）
 * @param rootIds - 要收集的根节点 ID 数组（通常是被编辑消息的 childrenIds）
 * @returns 被删除消息的埋点数据数组
 */
export const collectDeletedMessagesForTracking = (
	messages: Record<string, any>,
	rootIds: string[]
): DeletedMessageTrackingData[] => {
	const result: DeletedMessageTrackingData[] = [];

	const collectRecursive = (nodeId: string) => {
		const node = messages[nodeId];
		if (!node) return;

		// 收集当前节点信息
		result.push({
			messageId: node.id,
			role: node.role,
			modelId: node.model ?? '',
			modelName: node.modelName || node.model || '',
			isUserModel: node.is_user_model ?? false,
			contentLength: node.content?.length ?? 0
		});

		// 递归收集子节点
		const children = node.childrenIds ?? [];
		for (const childId of children) {
			collectRecursive(childId);
		}
	};

	// 从所有根节点开始收集
	for (const rootId of rootIds) {
		collectRecursive(rootId);
	}

	return result;
};

/** 编辑用户消息并重新发送埋点参数类型 */
interface UserMessageEditAndResendParams {
	chatId: string;
	userMessageId: string;
	originalContentLength: number;
	newContentLength: number;
	hasContentChanged: boolean;
	deletedMessages: DeletedMessageTrackingData[];
	hasFilesBefore: boolean;
	hasFilesAfter: boolean;
	fileCountBefore: number;
	fileCountAfter: number;
}

/**
 * 埋点6：user_message_edit_resend
 *
 * 【埋点时机】用户编辑用户消息并点击发送，删除旧响应之前
 * 【UI 操作】点击用户消息编辑按钮 → 修改内容 → 点击发送
 * 【业务环节】editMessage() submit=true → 【埋点】→ 删除子消息 → sendMessage()
 * 【埋点数据】
 *   === 关联标识 ===
 *   - chat_id: string - 聊天 ID
 *   - user_message_id: string - 被编辑的用户消息 ID
 *
 *   === 时间信息 ===
 *   - edited_at: string - 编辑时间 (ISO 8601)
 *
 *   === 内容变化 ===
 *   - original_content_length: number - 原始内容字符数
 *   - new_content_length: number - 新内容字符数
 *   - has_content_changed: boolean - 内容是否改变
 *
 *   === 被剪枝的消息（整个子树）===
 *   - deleted_messages: array - 被删除的所有消息数组（包括 user 和 assistant）
 *       - message_id: string - 消息 ID
 *       - role: string - 消息角色 (user/assistant)
 *       - model_id: string - 模型 ID（仅 assistant 有值）
 *       - model_name: string - 模型名称（仅 assistant 有值）
 *       - is_user_model: boolean - 是否为私有模型
 *       - content_length: number - 消息内容字符数
 *   - deleted_message_count: number - 被删除消息总数
 *
 *   === 文件变化 ===
 *   - has_files_before: boolean - 编辑前是否有文件
 *   - has_files_after: boolean - 编辑后是否有文件
 *   - file_count_before: number - 编辑前文件数
 *   - file_count_after: number - 编辑后文件数
 *
 * @param params - 埋点参数
 */
export const trackUserMessageEditAndResend = (params: UserMessageEditAndResendParams) => {
	if (typeof window === 'undefined') return;
	console.log('user_message_edit_resend')

	posthog.capture('user_message_edit_resend', {
		// 关联标识
		chat_id: params.chatId,
		user_message_id: params.userMessageId,

		// 时间信息
		edited_at: new Date().toISOString(),

		// 内容变化
		original_content_length: params.originalContentLength,
		new_content_length: params.newContentLength,
		has_content_changed: params.hasContentChanged,

		// 被剪枝的消息（整个子树）
		deleted_messages: params.deletedMessages,
		deleted_message_count: params.deletedMessages.length,

		// 文件变化
		has_files_before: params.hasFilesBefore,
		has_files_after: params.hasFilesAfter,
		file_count_before: params.fileCountBefore,
		file_count_after: params.fileCountAfter
	});
};

/** 编辑用户消息并保存埋点参数类型（仅保存，不重新发送） */
interface UserMessageEditAndSaveParams {
	chatId: string;
	userMessageId: string;
	originalContentLength: number;
	newContentLength: number;
	hasContentChanged: boolean;
	hasFilesBefore: boolean;
	hasFilesAfter: boolean;
	fileCountBefore: number;
	fileCountAfter: number;
}

/**
 * 埋点7：user_message_edit_save
 *
 * 【埋点时机】用户编辑用户消息后点击"保存"按钮（不重新发送）
 * 【UI 操作】点击用户消息编辑按钮 → 修改内容 → 点击保存
 * 【业务环节】editMessage() submit=false 分支 → 【埋点】→ updateChat()
 * 【埋点数据】
 *   === 关联标识 ===
 *   - chat_id: string - 聊天 ID
 *   - user_message_id: string - 被编辑的用户消息 ID
 *
 *   === 时间信息 ===
 *   - saved_at: string - 保存时间 (ISO 8601)
 *
 *   === 内容变化 ===
 *   - original_content_length: number - 原始内容字符数
 *   - new_content_length: number - 新内容字符数
 *   - has_content_changed: boolean - 内容是否改变
 *
 *   === 文件变化 ===
 *   - has_files_before: boolean - 保存前是否有文件
 *   - has_files_after: boolean - 保存后是否有文件
 *   - file_count_before: number - 保存前文件数
 *   - file_count_after: number - 保存后文件数
 *
 * @param params - 埋点参数
 */
export const trackUserMessageEditAndSave = (params: UserMessageEditAndSaveParams) => {
	if (typeof window === 'undefined') return;

	console.log('user_message_edit_save')
	posthog.capture('user_message_edit_save', {
		// 关联标识
		chat_id: params.chatId,
		user_message_id: params.userMessageId,

		// 时间信息
		saved_at: new Date().toISOString(),

		// 内容变化
		original_content_length: params.originalContentLength,
		new_content_length: params.newContentLength,
		has_content_changed: params.hasContentChanged,

		// 文件变化
		has_files_before: params.hasFilesBefore,
		has_files_after: params.hasFilesAfter,
		file_count_before: params.fileCountBefore,
		file_count_after: params.fileCountAfter
	});
};

/** 编辑助手消息并保存埋点参数类型 */
interface AssistantMessageEditAndSaveParams {
	chatId: string;
	assistantMessageId: string;
	userMessageId: string;
	originalContentLength: number;
	newContentLength: number;
	modelId: string;
	modelName: string;
	isUserModel: boolean;
}

/**
 * 埋点8：assistant_message_edit_save
 *
 * 【埋点时机】用户编辑助手消息内容并保存
 * 【UI 操作】点击助手消息编辑按钮 → 修改内容 → 保存
 * 【业务环节】editMessage() else 分支 → 【埋点】→ updateChat()
 * 【埋点数据】
 *   === 关联标识 ===
 *   - chat_id: string - 聊天 ID
 *   - assistant_message_id: string - 被编辑的助手消息 ID
 *   - user_message_id: string - 关联的用户消息 ID（父消息）
 *
 *   === 时间信息 ===
 *   - saved_at: string - 保存时间 (ISO 8601)
 *
 *   === 内容变化 ===
 *   - original_content_length: number - 原始内容字符数
 *   - new_content_length: number - 新内容字符数
 *
 *   === 模型信息 ===
 *   - model_id: string - 生成该响应的模型 ID
 *   - model_name: string - 模型名称
 *   - is_user_model: boolean - 是否为用户私有模型
 *
 * @param params - 埋点参数
 */
export const trackAssistantMessageEditAndSave = (params: AssistantMessageEditAndSaveParams) => {
	if (typeof window === 'undefined') return;
	console.log('assistant_message_edit_save')
	posthog.capture('assistant_message_edit_save', {
		// 关联标识
		chat_id: params.chatId,
		assistant_message_id: params.assistantMessageId,
		user_message_id: params.userMessageId,

		// 时间信息
		saved_at: new Date().toISOString(),

		// 内容变化
		original_content_length: params.originalContentLength,
		new_content_length: params.newContentLength,

		// 模型信息
		model_id: params.modelId,
		model_name: params.modelName,
		is_user_model: params.isUserModel
	});
};

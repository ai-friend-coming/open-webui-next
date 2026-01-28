<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';
	import { PaneGroup, Pane, PaneResizer } from 'paneforge';

	import { getContext, onDestroy, onMount, tick } from 'svelte';
	const i18n: Writable<i18nType> = getContext('i18n');

	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { get, type Unsubscriber, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import {
		chatId,
		chats,
		config,
		type Model,
		models,
		userModels,
		tags as allTags,
		settings,
		showSidebar,
		WEBUI_NAME,
		banners,
		user,
		socket,
		showControls,
		showCallOverlay,
		currentChatPage,
		temporaryChatEnabled,
		mobile,
		isMobileDevice,
		showOverview,
		chatTitle,
		showArtifacts,
		tools,
		toolServers,
		functions,
		selectedFolder,
		pinnedChats,
		showEmbeds,
		stoppedMessageIds
	} from '$lib/stores';
	import {
		convertMessagesToHistory,
		copyToClipboard,
		getMessageContentParts,
		createMessagesList,
		getPromptVariables,
		processDetails,
		removeAllDetails
	} from '$lib/utils';

	import {
		createNewChat,
		getAllTags,
		getChatById,
		getChatList,
		getPinnedChatList,
		getTagsById,
		updateChatById,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import { generateOpenAIChatCompletion } from '$lib/apis/openai';
	import { processWeb, processWebSearch, processYoutubeVideo } from '$lib/apis/retrieval';
	import { getAndUpdateUserLocation, getUserSettings } from '$lib/apis/users';
	import {
		chatCompleted,
		generateQueries,
		chatAction,
		generateMoACompletion,
		stopTask,
		getTaskIdsByChatId
	} from '$lib/apis';
	import { getTools } from '$lib/apis/tools';
	import { uploadFile } from '$lib/apis/files';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import { SendingRequestManagement } from './SendingRequestManagement';

	import { fade } from 'svelte/transition';

	import Banner from '../common/Banner.svelte';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import ChatControls from './ChatControls.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Modal from '../common/Modal.svelte';
	import { getFunctions } from '$lib/apis/functions';
	import Image from '../common/Image.svelte';
	import { updateFolderById } from '$lib/apis/folders';
	import {
		trackChatOpened,
		trackMessageRegenerated,
		parseChatForTracking
	} from '$lib/posthog';

	export let chatIdProp = '';

	let loading = true;

	const eventTarget = new EventTarget();
	let controlPane;
	let controlPaneComponent;

	let messageInput;

	let autoScroll = true;
	let processing = '';
	let messagesContainerElement: HTMLDivElement;

	let navbarElement;

	let showEventConfirmation = false;
	let eventConfirmationTitle = '';
	let eventConfirmationMessage = '';
	let eventConfirmationInput = false;
	let eventConfirmationInputPlaceholder = '';
	let eventConfirmationInputValue = '';
	let eventCallback = null;

	// Perf Log Modal 状态
	let showPerfLogModal = false;
	let latestPerfLog: { timestamp: number; messageId: string; data: any } | null = null;

	let chatIdUnsubscriber: Unsubscriber | undefined;
	const sendingRequestManagement = new SendingRequestManagement();
	let isWaitingForResponse = false;
	const currentRequestId = sendingRequestManagement.currentRequestId;
	$: isWaitingForResponse = $currentRequestId !== null;

	// 订阅超时事件
	const timeoutEvent = sendingRequestManagement.timeoutEvent;
	$: if ($timeoutEvent) {
		handleTimeoutEvent($timeoutEvent);
	}

	let selectedModels = [''];
	let atSelectedModel: Model | undefined;
	let selectedModelIds = [];
	$: selectedModelIds = atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels;

	let selectedToolIds = [];
	let selectedFilterIds = [];
	let imageGenerationEnabled = false;
	let webSearchEnabled = false;
	let codeInterpreterEnabled = false;
	let memoryEnabled = true;
	let memoryLocked = false;

	let showCommands = false;

	let chat = null;
	let tags = [];

	// Session-specific model name customization
	let customModelNames = {}; // { "model-id": "Custom Name" }

	let history = {
		messages: {},
		currentId: null
	};

	// Chat Input
	let prompt = '';
	let chatFiles = [];
	let files = [];
	let params = {};

	$: if (chatIdProp) {
		navigateHandler();
	}

	const navigateHandler = async () => {
		loading = true;

		const isMobile = isMobileDevice();

		prompt = '';
		messageInput?.setText('', undefined, { focusInput: !isMobile });

		files = [];
		selectedToolIds = [];
		selectedFilterIds = [];
		webSearchEnabled = false;
		imageGenerationEnabled = false;
		memoryEnabled = true;
		memoryLocked = false;

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		if (chatIdProp && (await loadChat())) {
			await tick();
			loading = false;
			window.setTimeout(() => scrollToBottom(), 0);

			await tick();

			if (storageChatInput) {
				try {
					const input = JSON.parse(storageChatInput);

					if (!$temporaryChatEnabled) {
						messageInput?.setText(input.prompt, undefined, { focusInput: !isMobile });
						files = input.files;
						selectedToolIds = input.selectedToolIds;
						selectedFilterIds = input.selectedFilterIds;
						webSearchEnabled = input.webSearchEnabled;
						imageGenerationEnabled = input.imageGenerationEnabled;
						codeInterpreterEnabled = input.codeInterpreterEnabled;
						if (!memoryLocked) {
							memoryEnabled = input.memoryEnabled;
						}
					}
				} catch (e) {}
			}

			if (!isMobile) {
				const chatInput = document.getElementById('chat-input');
				chatInput?.focus();
			}
		} else {
			await goto('/');
		}
	};

	const onSelect = async (e) => {
		const { type, data } = e;

		if (type === 'prompt') {
			// Handle prompt selection
			messageInput?.setText(data, async () => {
				if (!($settings?.insertSuggestionPrompt ?? false)) {
					await tick();
					submitPrompt(prompt);
				}
			});
		}
	};

	$: if (selectedModels && chatIdProp !== '') {
		saveSessionSelectedModels();
	}

	const saveSessionSelectedModels = () => {
		const selectedModelsString = JSON.stringify(selectedModels);
		if (
			selectedModels.length === 0 ||
			(selectedModels.length === 1 && selectedModels[0] === '') ||
			sessionStorage.selectedModels === selectedModelsString
		) {
			return;
		}
		sessionStorage.selectedModels = selectedModelsString;
		console.log('saveSessionSelectedModels', selectedModels, sessionStorage.selectedModels);
	};

	let oldSelectedModelIds = [''];
	$: if (JSON.stringify(selectedModelIds) !== JSON.stringify(oldSelectedModelIds)) {
		onSelectedModelIdsChange();
	}

	const onSelectedModelIdsChange = () => {
		if (oldSelectedModelIds.filter((id) => id).length > 0) {
			resetInput();
		}
		oldSelectedModelIds = selectedModelIds;
	};

	const resetInput = () => {
		selectedToolIds = [];
		selectedFilterIds = [];
		webSearchEnabled = false;
		imageGenerationEnabled = false;
		codeInterpreterEnabled = false;
		// memoryEnabled = true;

		setDefaults();
	};

	const setDefaults = async () => {
		if (!$tools) {
			tools.set(await getTools(localStorage.token));
		}
		if (!$functions) {
			functions.set(await getFunctions(localStorage.token));
		}
		if (selectedModels.length !== 1 && !atSelectedModel) {
			return;
		}

		const model = atSelectedModel ?? $models.find((m) => m.id === selectedModels[0]);
		if (model) {
			// Set Default Tools
			if (model?.info?.meta?.toolIds) {
				selectedToolIds = [
					...new Set(
						[...(model?.info?.meta?.toolIds ?? [])].filter((id) => $tools.find((t) => t.id === id))
					)
				];
			}

			// Set Default Filters (Toggleable only)
			if (model?.info?.meta?.defaultFilterIds) {
				selectedFilterIds = model.info.meta.defaultFilterIds.filter((id) =>
					model?.filters?.find((f) => f.id === id)
				);
			}

			// Set Default Features
			if (model?.info?.meta?.defaultFeatureIds) {
				if (model.info?.meta?.capabilities?.['image_generation']) {
					imageGenerationEnabled = model.info.meta.defaultFeatureIds.includes('image_generation');
				}

				if (model.info?.meta?.capabilities?.['web_search']) {
					webSearchEnabled = model.info.meta.defaultFeatureIds.includes('web_search');
				}

				if (model.info?.meta?.capabilities?.['code_interpreter']) {
					codeInterpreterEnabled = model.info.meta.defaultFeatureIds.includes('code_interpreter');
				}

				// if (model.info?.meta?.capabilities?.['memory']) {
				// 	memoryEnabled = model.info.meta.defaultFeatureIds.includes('memory');
				// }
			}
		}
	};

	const showMessage = async (message, ignoreSettings = false) => {
		await tick();

		const _chatId = JSON.parse(JSON.stringify($chatId));
		let _messageId = JSON.parse(JSON.stringify(message.id));

		let messageChildrenIds = [];
		if (_messageId === null) {
			messageChildrenIds = Object.keys(history.messages).filter(
				(id) => history.messages[id].parentId === null
			);
		} else {
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		while (messageChildrenIds.length !== 0) {
			_messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		history.currentId = _messageId;

		await tick();
		await tick();
		await tick();

		if (($settings?.scrollOnBranchChange ?? true) || ignoreSettings) {
			const messageElement = document.getElementById(`message-${message.id}`);
			if (messageElement) {
				messageElement.scrollIntoView({ behavior: 'smooth' });
			}
		}

		await tick();
		saveChatHandler(_chatId, history);
	};

	/**
	 * 处理超时事件
	 * 当请求超时时，标记消息为 broken 状态
	 *
	 * @param messageId - 超时的消息 ID
	 */
	const handleTimeoutEvent = async (messageId: string) => {
		console.log(`[Chat] Handling timeout event for message ${messageId}`);

		const message = history.messages[messageId];
		if (!message) {
			// 清空事件（避免重复处理）
			sendingRequestManagement.timeoutEvent.set(null);
			return;
		}

		// 标记消息为 broken 状态
		message.broken = true;

		// 标记父消息完成
		const parentId = message.parentId;
		if (parentId && history.messages[parentId]) {
			history.messages[parentId].done = true;
		}

		// 保存更新后的 history 到数据库
		// 注意：createMessagesList 会过滤掉 broken 消息，因此不会持久化
		await saveChatHandler($chatId, history);

		// 清空事件（避免重复处理）
		sendingRequestManagement.timeoutEvent.set(null);
	};

	/**
	 * 聊天页 WebSocket 事件处理器
	 * ========================================
	 * 处理当前聊天会话的所有 WS 事件，更新消息内容/状态/错误等
	 *
	 * 事件来源：后端通过 Socket.IO 'events' 通道推送
	 * 绑定位置：onMount 中 $socket?.on('events', chatEventHandler)
	 * 解绑位置：onDestroy 中 $socket?.off('events', chatEventHandler)
	 *
	 * @param event - WS 事件对象，包含 chat_id, message_id, data: { type, data }
	 * @param cb - 可选回调，用于 confirmation/execute/input 等需要响应的事件
	 */
	const chatEventHandler = async (event, cb) => {
		// console.log(event);

		// 只处理当前聊天的事件（通过 chat_id 过滤）
		if (event.chat_id === $chatId) {
			await tick();
			let message = history.messages[event.message_id];

			if (message) {
				const type = event?.data?.type ?? null;
				const data = event?.data?.data ?? null;

				// ========== 状态事件 ==========
				// 追加到消息的状态历史（如 knowledge_search 进度、工具执行状态等）
				if (type === 'status') {
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
					// ========== LLM 响应事件 ==========
					// 委托给专门的处理器，处理流式/非流式响应、usage、sources 等
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, message, event.chat_id);
					// ========== 任务取消事件 ==========
					// 用户点击停止或后端异常时触发，清理生成状态
				} else if (type === 'chat:tasks:cancel') {
					if (event.message_id) {
						sendingRequestManagement.handleWsChatTasksCancel(event.message_id);
					}

					if (event.message_id === history.currentId) {
						const responseMessage = history.messages[history.currentId];
						// Set all response messages to done
						for (const messageId of history.messages[responseMessage.parentId].childrenIds) {
							history.messages[messageId].done = true;
						}
					}
				} else if (type === 'chat:message:delta' || type === 'message') {
					message.content += data.content;
					// ========== 消息内容替换 ==========
					// 完全替换消息内容（非增量）
				} else if (type === 'chat:message' || type === 'replace') {
					message.content = data.content;
					// ========== 文件附件更新 ==========
				} else if (type === 'chat:message:files' || type === 'files') {
					message.files = data.files;
					// ========== 嵌入内容更新 ==========
				} else if (type === 'chat:message:embeds' || type === 'embeds') {
					message.embeds = data.embeds;
					// ========== 错误处理 ==========
					// 后端处理失败时触发，需要回滚消息并清理状态
				} else if (type === 'chat:message:error') {
					// 检查消息是否已被用户停止
					if ($stoppedMessageIds.has(event.message_id)) {
						stoppedMessageIds.update((ids) => {
							ids.delete(event.message_id);
							return ids;
						});
						return; // 跳过错误处理
					}

					// --- 生命周期追踪：WS 错误 ---
					if (event.message_id) {
						sendingRequestManagement.handleWsChatMessageError(event.message_id, data.error);
					}

					// 显示 Toast 通知用户错误
					toast.error(data.error?.content || $i18n.t('An error occurred'));

					// 从 history 中删除这条错误消息
					const parentId = message.parentId;
					if (parentId && history.messages[parentId]) {
						// 从父消息的 childrenIds 中移除
						history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
							(id) => id !== message.id
						);
					}

					// 删除消息本身
					delete history.messages[message.id];

					// 如果这是当前消息，重置 currentId 到父消息
					if (history.currentId === message.id) {
						history.currentId = parentId;
					}

					// v3: 给父消息（用户消息）添加 done=true，确保按钮状态正确
					if (parentId && history.messages[parentId]) {
						history.messages[parentId].done = true;
					}

					// 保存更新后的 history 到数据库
					await saveChatHandler($chatId, history);
					// ========== 后续问题建议 ==========
					// 后端生成的建议性后续问题，显示在消息下方
				} else if (type === 'chat:message:follow_ups') {
					message.followUps = data.follow_ups;

					if (autoScroll) {
						scrollToBottom('smooth');
					}
					// ========== 聊天标题更新 ==========
					// 后端自动生成标题后推送，更新侧边栏列表
				} else if (type === 'chat:title') {
					chatTitle.set(data);
					currentChatPage.set(1);
					await chats.set(await getChatList(localStorage.token, $currentChatPage));
					// ========== 聊天标签更新 ==========
					// 后端自动生成标签后推送
				} else if (type === 'chat:tags') {
					chat = await getChatById(localStorage.token, $chatId);
					allTags.set(await getAllTags(localStorage.token));
					// ========== 引用/来源信息 ==========
					// RAG 检索结果、代码执行结果等引用源
				} else if (type === 'source' || type === 'citation') {
					// 代码执行类型：按 ID 更新或新增
					if (data?.type === 'code_execution') {
						// Code execution; update existing code execution by ID, or add new one.
						if (!message?.code_executions) {
							message.code_executions = [];
						}

						const existingCodeExecutionIndex = message.code_executions.findIndex(
							(execution) => execution.id === data.id
						);

						if (existingCodeExecutionIndex !== -1) {
							message.code_executions[existingCodeExecutionIndex] = data;
						} else {
							message.code_executions.push(data);
						}

						message.code_executions = message.code_executions;
					} else {
						// 普通引用源：追加到 sources 数组
						// Regular source.
						if (message?.sources) {
							message.sources.push(data);
						} else {
							message.sources = [data];
						}
					}
					// ========== 通知事件 ==========
					// 后端推送的 toast 通知（成功/错误/警告/信息）
				} else if (type === 'notification') {
					const toastType = data?.type ?? 'info';
					const toastContent = data?.content ?? '';

					if (toastType === 'success') {
						toast.success(toastContent);
					} else if (toastType === 'error') {
						toast.error(toastContent);
					} else if (toastType === 'warning') {
						toast.warning(toastContent);
					} else {
						toast.info(toastContent);
					}
					// ========== 性能日志 ==========
					// 开发调试用：输出性能日志到控制台
				} else if (type === 'chat:perf_log') {
					// 存储最新的 perf_log 数据
					latestPerfLog = {
						timestamp: Date.now(),
						messageId: event.message_id,
						data: data
					};

					// 开发调试用：输出性能日志到控制台
					console.group('🔧 Performance Log');
					console.log('Message ID:', event.message_id);
					console.log('Full Data:', data);
					console.groupEnd();

					// 可选：存储到 window 对象供调试
					if (typeof window !== 'undefined') {
						window.__PERF_LOGS__ = window.__PERF_LOGS__ || [];
						window.__PERF_LOGS__.push({
							timestamp: Date.now(),
							messageId: event.message_id,
							data: data
						});
					}
					// ========== 确认对话框 ==========
					// 后端请求用户确认某操作，需要通过 cb 回调结果
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					// ========== 执行代码 ==========
					// 后端下发 JS 代码让前端执行（用于插件/工具扩展）
				} else if (type === 'execute') {
					eventCallback = cb;

					try {
						// Use Function constructor to evaluate code in a safer way
						const asyncFunction = new Function(`return (async () => { ${data.code} })()`);
						const result = await asyncFunction(); // Await the result of the async function

						if (cb) {
							cb(result);
						}
					} catch (error) {
						console.error('Error executing code:', error);
					}
					// ========== 输入对话框 ==========
					// 后端请求用户输入内容，需要通过 cb 回调用户输入
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
					// ========== 未知事件类型 ==========
				} else {
					console.log('Unknown message type', data);
				}

				history.messages[event.message_id] = message;
			}
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		if (event.origin !== window.origin) {
			return;
		}

		if (event.data.type === 'action:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitPrompt(prompt);
			}
		}

		// Replace with your iframe's origin
		if (event.data.type === 'input:prompt') {
			console.debug(event.data.text);

			const inputElement = document.getElementById('chat-input');

			if (inputElement) {
				messageInput?.setText(event.data.text);
				inputElement.focus();
			}
		}

		if (event.data.type === 'input:prompt:submit') {
			console.debug(event.data.text);

			if (event.data.text !== '') {
				await tick();
				submitPrompt(event.data.text);
			}
		}
	};

	const savedModelIds = async () => {
		if (
			$selectedFolder &&
			selectedModels.filter((modelId) => modelId !== '').length > 0 &&
			JSON.stringify($selectedFolder?.data?.model_ids) !== JSON.stringify(selectedModels)
		) {
			const res = await updateFolderById(localStorage.token, $selectedFolder.id, {
				data: {
					model_ids: selectedModels
				}
			});
		}
	};

	$: if (selectedModels !== null) {
		savedModelIds();
	}

	let pageSubscribe = null;
	let showControlsSubscribe = null;
	let selectedFolderSubscribe = null;

	/**
	 * 组件挂载生命周期
	 * ========================================
	 * 初始化 WS 事件监听、路由订阅、输入状态恢复等
	 */
	onMount(async () => {
		loading = true;
		console.log('mounted');

		// ========== 事件监听绑定 ==========
		// 1. postMessage 监听：用于跨窗口/iframe 通信
		window.addEventListener('message', onMessageHandler);
		// 2. Socket.IO 'events' 监听：接收后端推送的聊天事件
		//    事件由 chatEventHandler 处理，包括消息更新、状态变更、错误等
		$socket?.on('events', chatEventHandler);

		pageSubscribe = page.subscribe(async (p) => {
			if (p.url.pathname === '/') {
				await tick();
				initNewChat();
			}
		});

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		if (!chatIdProp) {
			loading = false;
			await tick();
		}

		const isMobile = isMobileDevice();

		if (storageChatInput) {
			prompt = '';
			messageInput?.setText('', undefined, { focusInput: !isMobile });

			files = [];
			selectedToolIds = [];
			selectedFilterIds = [];
			webSearchEnabled = false;
			imageGenerationEnabled = false;
			codeInterpreterEnabled = false;
			memoryEnabled = true;

			try {
				const input = JSON.parse(storageChatInput);

				if (!$temporaryChatEnabled) {
					messageInput?.setText(input.prompt, undefined, { focusInput: !isMobile });
					files = input.files;
					selectedToolIds = input.selectedToolIds;
					selectedFilterIds = input.selectedFilterIds;
					webSearchEnabled = input.webSearchEnabled;
					imageGenerationEnabled = input.imageGenerationEnabled;
					codeInterpreterEnabled = input.codeInterpreterEnabled;
					memoryEnabled = input.memoryEnabled;
				}
			} catch (e) {}
		}

		showControlsSubscribe = showControls.subscribe(async (value) => {
			if (controlPane && !$mobile) {
				try {
					if (value) {
						controlPaneComponent.openPane();
					} else {
						controlPane.collapse();
					}
				} catch (e) {
					// ignore
				}
			}

			if (!value) {
				showCallOverlay.set(false);
				showOverview.set(false);
				showArtifacts.set(false);
				showEmbeds.set(false);
			}
		});

		selectedFolderSubscribe = selectedFolder.subscribe(async (folder) => {
			if (
				folder?.data?.model_ids &&
				JSON.stringify(selectedModels) !== JSON.stringify(folder.data.model_ids)
			) {
				selectedModels = folder.data.model_ids;

				console.log('Set selectedModels from folder data:', selectedModels);
			}
		});

		// 移动端不自动聚焦，避免键盘弹出
		if (!isMobile) {
			const chatInput = document.getElementById('chat-input');
			chatInput?.focus();
		}
	});

	/**
	 * 组件销毁生命周期
	 * ========================================
	 * 清理所有事件监听和订阅，防止内存泄漏和重复处理
	 */
	onDestroy(() => {
		try {
			// ========== 订阅取消 ==========
			pageSubscribe();
			showControlsSubscribe();
			selectedFolderSubscribe();
			chatIdUnsubscriber?.();

			// ========== 事件监听解绑 ==========
			// 1. postMessage 监听解绑
			window.removeEventListener('message', onMessageHandler);
			// 2. Socket.IO 'events' 监听解绑
			//    必须解绑，否则组件销毁后仍会处理事件，导致错误和内存泄漏
			$socket?.off('events', chatEventHandler);
		} catch (e) {
			console.error(e);
		}
	});

	// File upload functions

	const uploadGoogleDriveFile = async (fileData) => {
		console.log('Starting uploadGoogleDriveFile with:', {
			id: fileData.id,
			name: fileData.name,
			url: fileData.url,
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		// Validate input
		if (!fileData?.id || !fileData?.name || !fileData?.url || !fileData?.headers?.Authorization) {
			throw new Error('Invalid file data provided');
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: fileData.url,
			name: fileData.name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: 0
		};

		try {
			files = [...files, fileItem];
			console.log('Processing web file with URL:', fileData.url);

			// Configure fetch options with proper headers
			const fetchOptions = {
				headers: {
					Authorization: fileData.headers.Authorization,
					Accept: '*/*'
				},
				method: 'GET'
			};

			// Attempt to fetch the file
			console.log('Fetching file content from Google Drive...');
			const fileResponse = await fetch(fileData.url, fetchOptions);

			if (!fileResponse.ok) {
				const errorText = await fileResponse.text();
				throw new Error(`Failed to fetch file (${fileResponse.status}): ${errorText}`);
			}

			// Get content type from response
			const contentType = fileResponse.headers.get('content-type') || 'application/octet-stream';
			console.log('Response received with content-type:', contentType);

			// Convert response to blob
			console.log('Converting response to blob...');
			const fileBlob = await fileResponse.blob();

			if (fileBlob.size === 0) {
				throw new Error('Retrieved file is empty');
			}

			console.log('Blob created:', {
				size: fileBlob.size,
				type: fileBlob.type || contentType
			});

			// Create File object with proper MIME type
			const file = new File([fileBlob], fileData.name, {
				type: fileBlob.type || contentType
			});

			console.log('File object created:', {
				name: file.name,
				size: file.size,
				type: file.type
			});

			if (file.size === 0) {
				throw new Error('Created file is empty');
			}

			// If the file is an audio file, provide the language for STT.
			let metadata = null;
			if (
				(file.type.startsWith('audio/') || file.type.startsWith('video/')) &&
				$settings?.audio?.stt?.language
			) {
				metadata = {
					language: $settings?.audio?.stt?.language
				};
			}

			// Upload file to server
			console.log('Uploading file to server...');
			const uploadedFile = await uploadFile(localStorage.token, file, metadata);

			if (!uploadedFile) {
				throw new Error('Server returned null response for file upload');
			}

			console.log('File uploaded successfully:', uploadedFile);

			// Update file item with upload results
			fileItem.status = 'uploaded';
			fileItem.file = uploadedFile;
			fileItem.id = uploadedFile.id;
			fileItem.size = file.size;
			fileItem.collection_name = uploadedFile?.meta?.collection_name;
			fileItem.url = `${WEBUI_API_BASE_URL}/files/${uploadedFile.id}`;

			files = files;
			toast.success($i18n.t('File uploaded successfully'));
		} catch (e) {
			console.error('Error uploading file:', e);
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error(
				$i18n.t('Error uploading file: {{error}}', {
					error: e.message || 'Unknown error'
				})
			);
		}
	};

	const uploadWeb = async (url) => {
		console.log(url);

		const fileItem = {
			type: 'text',
			name: url,
			collection_name: '',
			status: 'uploading',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processWeb(localStorage.token, '', url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};

				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(JSON.stringify(e));
		}
	};

	const uploadYoutubeTranscription = async (url) => {
		console.log(url);

		const fileItem = {
			type: 'text',
			name: url,
			collection_name: '',
			status: 'uploading',
			context: 'full',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processYoutubeVideo(localStorage.token, url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};
				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(`${e}`);
		}
	};

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		console.log('initNewChat');
		if ($user?.role !== 'admin' && $user?.permissions?.chat?.temporary_enforced) {
			await temporaryChatEnabled.set(true);
		}

		if ($settings?.temporaryChatByDefault ?? false) {
			if ($temporaryChatEnabled === false) {
				await temporaryChatEnabled.set(true);
			} else if ($temporaryChatEnabled === null) {
				// if set to null set to false; refer to temp chat toggle click handler
				await temporaryChatEnabled.set(false);
			}
		}

		const availableModels = $models
			.filter((m) => !(m?.info?.meta?.hidden ?? false))
			.map((m) => m.id);

		if ($page.url.searchParams.get('models') || $page.url.searchParams.get('model')) {
			const urlModels = (
				$page.url.searchParams.get('models') ||
				$page.url.searchParams.get('model') ||
				''
			)?.split(',');

			if (urlModels.length === 1) {
				const m = $models.find((m) => m.id === urlModels[0]);
				if (!m) {
					const modelSelectorButton = document.getElementById('model-selector-0-button');
					if (modelSelectorButton) {
						modelSelectorButton.click();
						await tick();

						const modelSelectorInput = document.getElementById('model-search-input');
						if (modelSelectorInput) {
							modelSelectorInput.focus();
							modelSelectorInput.value = urlModels[0];
							modelSelectorInput.dispatchEvent(new Event('input'));
						}
					}
				} else {
					selectedModels = urlModels;
				}
			} else {
				selectedModels = urlModels;
			}

			selectedModels = selectedModels.filter((modelId) =>
				$models.map((m) => m.id).includes(modelId)
			);
		} else {
			if ($selectedFolder?.data?.model_ids) {
				selectedModels = $selectedFolder?.data?.model_ids;
			} else {
				if (sessionStorage.selectedModels) {
					selectedModels = JSON.parse(sessionStorage.selectedModels);
					sessionStorage.removeItem('selectedModels');
				} else {
					if ($settings?.models) {
						selectedModels = $settings?.models;
					} else if ($config?.default_models) {
						console.log($config?.default_models.split(',') ?? '');
						selectedModels = $config?.default_models.split(',');
					}
				}
			}

			selectedModels = selectedModels.filter((modelId) => availableModels.includes(modelId));
		}

		if (selectedModels.length === 0 || (selectedModels.length === 1 && selectedModels[0] === '')) {
			if (availableModels.length > 0) {
				selectedModels = [availableModels?.at(0) ?? ''];
			} else {
				selectedModels = [''];
			}
		}

		await showControls.set(false);
		await showCallOverlay.set(false);
		await showOverview.set(false);
		await showArtifacts.set(false);

		if ($page.url.pathname.includes('/c/')) {
			window.history.replaceState(history.state, '', `/`);
		}

		autoScroll = true;

		resetInput();
		await chatId.set('');
		await chatTitle.set('');

		history = {
			messages: {},
			currentId: null
		};

		chatFiles = [];
		params = {};

		// Reset session-specific custom model names
		customModelNames = {};

		if ($page.url.searchParams.get('youtube')) {
			uploadYoutubeTranscription(
				`https://www.youtube.com/watch?v=${$page.url.searchParams.get('youtube')}`
			);
		}

		if ($page.url.searchParams.get('load-url')) {
			await uploadWeb($page.url.searchParams.get('load-url'));
		}

		if ($page.url.searchParams.get('web-search') === 'true') {
			webSearchEnabled = true;
		}

		if ($page.url.searchParams.get('image-generation') === 'true') {
			imageGenerationEnabled = true;
		}

		if ($page.url.searchParams.get('code-interpreter') === 'true') {
			codeInterpreterEnabled = true;
		}

		if ($page.url.searchParams.get('tools')) {
			selectedToolIds = $page.url.searchParams
				.get('tools')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		} else if ($page.url.searchParams.get('tool-ids')) {
			selectedToolIds = $page.url.searchParams
				.get('tool-ids')
				?.split(',')
				.map((id) => id.trim())
				.filter((id) => id);
		}

		if ($page.url.searchParams.get('call') === 'true') {
			showCallOverlay.set(true);
			showControls.set(true);
		}

		if ($page.url.searchParams.get('q')) {
			const q = $page.url.searchParams.get('q') ?? '';
			messageInput?.setText(q);

			if (q) {
				if (($page.url.searchParams.get('submit') ?? 'true') === 'true') {
					await tick();
					submitPrompt(q);
				}
			}
		}

		selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);

		const userSettings = await getUserSettings(localStorage.token);

		if (userSettings) {
			settings.set(userSettings.ui);
		} else {
			settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
		}

		// 移动端不自动聚焦，避免键盘弹出
		if (!isMobileDevice()) {
			const chatInput = document.getElementById('chat-input');
			setTimeout(() => chatInput?.focus(), 0);
		}
	};

	const loadChat = async () => {
		chatId.set(chatIdProp);

		if ($temporaryChatEnabled) {
			temporaryChatEnabled.set(false);
		}

		chat = await getChatById(localStorage.token, $chatId).catch(async (error) => {
			await goto('/');
			return null;
		});

		if (chat) {
			tags = await getTagsById(localStorage.token, $chatId).catch(async (error) => {
				return [];
			});

			const chatContent = chat.chat;

			if (chatContent) {
				console.log(chatContent);
				console.log('[Memory Debug] chatContent.memory_enabled:', chatContent?.memory_enabled);

				const getLastModelId = (models: any) => {
					if (Array.isArray(models)) {
						const nonEmpty = models.filter((m) => !!m);
						return nonEmpty.length ? nonEmpty[nonEmpty.length - 1] : '';
					}
					return models ?? '';
				};

				const importedModelId = getLastModelId(chatContent?.models);
				selectedModels = [importedModelId];

				if (!($user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true))) {
					selectedModels = selectedModels.length > 0 ? [selectedModels[0]] : [''];
				}

				oldSelectedModelIds = selectedModels;

				history =
					(chatContent?.history ?? undefined) !== undefined
						? chatContent.history
						: convertMessagesToHistory(chatContent.messages);

				chatTitle.set(chatContent.title);

				const userSettings = await getUserSettings(localStorage.token);

				if (userSettings) {
					await settings.set(userSettings.ui);
				} else {
					await settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
				}

				params = chatContent?.params ?? {};
				chatFiles = chatContent?.files ?? [];

				// Load session-specific custom model names
				customModelNames = chat?.meta?.modelNames ?? {};

				if (chatContent?.memory_enabled !== undefined) {
					memoryEnabled = chatContent.memory_enabled;
					console.log('[Memory Debug] Set memoryEnabled from chatContent:', memoryEnabled);
				} else {
					console.log('[Memory Debug] memory_enabled is undefined, using default');
				}

				autoScroll = true;
				await tick();

				if (history.currentId) {
					for (const message of Object.values(history.messages)) {
						if (message.role === 'assistant') {
							message.done = true;
						}
					}
				}

				memoryLocked = Object.keys(history?.messages ?? {}).length > 0;
				
				// NotTODO:
				// const taskRes = await getTaskIdsByChatId(localStorage.token, $chatId).catch((error) => {
				// 	return null;
				// });

				// if (taskRes) {
				// 	taskIds = taskRes.task_ids;
				// }

				await tick();

				// 埋点：进入聊天窗
				trackChatOpened(chat);

				return true;
			} else {
				return null;
			}
		}
	};

	// Handler for renaming models in the current session
	const handleRenameModel = async (modelId: string, customName: string) => {
		if (customName === '') {
			// Remove custom name
			delete customModelNames[modelId];
		} else {
			// Set custom name
			customModelNames[modelId] = customName;
		}

		// Trigger reactivity
		customModelNames = { ...customModelNames };

		// Save to backend if chat exists
		if ($chatId && chat) {
			const updatedMeta = {
				...chat.meta,
				modelNames: customModelNames
			};

			await updateChatById(localStorage.token, $chatId, {
				meta: updatedMeta
			});

			// Update local chat object
			chat.meta = updatedMeta;
		}
	};

	const scrollToBottom = async (behavior = 'auto') => {
		await tick();
		if (messagesContainerElement) {
			messagesContainerElement.scrollTo({
				top: messagesContainerElement.scrollHeight,
				behavior
			});
		}
	};
	/**
	 * 聊天完成后处理器
	 * ========================================
	 * 在 LLM 响应完成后调用，负责：
	 *   1. 调用后端 /api/chat/completed 接口，触发后处理逻辑（如 Filter outlet）
	 *   2. 处理后端返回的消息更新（可能经过 Filter 修改）
	 *   3. 持久化聊天记录到数据库
	 *   4. 清理生成状态
	 *
	 * 调用时机：
	 *   - 流式响应结束后（done=true）
	 *   - 非流式响应接收后
	 *
	 * 后端位置：backend/open_webui/routers/chats.py - chat_completed
	 *
	 * @param chatId - 聊天 ID
	 * @param modelId - 使用的模型 ID
	 * @param responseMessageId - 助手响应消息的 ID
	 * @param messages - 本次对话的消息列表（用于发送给后端处理）
	 */
	const chatCompletedHandler = async (chatId, modelId, responseMessageId, messages) => {
		// ========== 1. 调用后端完成接口 ==========
		// 触发 Filter outlet、后处理插件等逻辑
		const res = await chatCompleted(localStorage.token, {
			model: modelId,
			// 构造精简的消息列表发送给后端
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.usage ? { usage: m.usage } : {}),
				...(m.sources ? { sources: m.sources } : {})
			})),
			filter_ids: selectedFilterIds.length > 0 ? selectedFilterIds : undefined,
			model_item: $models.find((m) => m.id === modelId),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch(async (error) => {
			// ========== 错误处理：回滚消息 ==========
			toast.error(`${error}`);

			// 生命周期追踪：chatCompleted API 调用失败
			sendingRequestManagement.failRequest(
				responseMessageId,
				{ errorType: 'completion_error', error: String(error) },
				'error'
			);
			// v2: 删除错误消息而不是设置 error 字段
			const errorMessage = history.messages[responseMessageId];
			if (errorMessage) {
				const parentId = errorMessage.parentId;
				// 从父消息的 childrenIds 中移除错误消息
				if (parentId && history.messages[parentId]) {
					// 从父消息的 childrenIds 中移除
					history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
						(id) => id !== responseMessageId
					);
				}

				// 删除消息本身
				delete history.messages[responseMessageId];

				// 如果这是当前消息，重置 currentId 到父消息
				if (history.currentId === responseMessageId) {
					history.currentId = parentId;
				}

				// v3: 给父消息（用户消息）添加 done=true，确保按钮状态正确
				if (parentId && history.messages[parentId]) {
					history.messages[parentId].done = true;
				}

				// 保存更新后的 history 到数据库
				await saveChatHandler($chatId, history);
			}

			return null;
		});

		// ========== 2. 处理后端返回的消息更新 ==========
		// 后端 Filter outlet 可能修改消息内容，需要同步更新
		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				if (message?.id) {
					// Add null check for message and message.id
					// 如果内容被修改，保留原始内容到 originalContent
					history.messages[message.id] = {
						...history.messages[message.id],
						...(history.messages[message.id].content !== message.content
							? { originalContent: history.messages[message.id].content }
							: {}),
						...message
					};
				}
			}
		}

		await tick();

		// ========== 3. 持久化聊天记录 ==========
		// 仅当仍在当前聊天且非临时聊天时保存
		if ($chatId == chatId) {
			if (!$temporaryChatEnabled) {
				const currentMessages = createMessagesList(history, history.currentId);
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: currentMessages,
					history: history,
					params: params,
					files: chatFiles
				});

				// 刷新侧边栏聊天列表
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const chatActionHandler = async (chatId, actionId, modelId, responseMessageId, event = null) => {
		const messages = createMessagesList(history, responseMessageId);

		const res = await chatAction(localStorage.token, actionId, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			...(event ? { event: event } : {}),
			model_item: $models.find((m) => m.id === modelId),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch(async (error) => {
			toast.error(`${error}`);

			// v2: 删除错误消息而不是设置 error 字段
			const errorMessage = history.messages[responseMessageId];
			if (errorMessage) {
				const parentId = errorMessage.parentId;
				if (parentId && history.messages[parentId]) {
					// 从父消息的 childrenIds 中移除
					history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
						(id) => id !== responseMessageId
					);
				}

				// 删除消息本身
				delete history.messages[responseMessageId];

				// 如果这是当前消息，重置 currentId 到父消息
				if (history.currentId === responseMessageId) {
					history.currentId = parentId;
				}

				// v3: 给父消息（用户消息）添加 done=true，确保按钮状态正确
				if (parentId && history.messages[parentId]) {
					history.messages[parentId].done = true;
				}

				// 保存更新后的 history 到数据库
				await saveChatHandler($chatId, history);
			}

			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				history.messages[message.id] = {
					...history.messages[message.id],
					...(history.messages[message.id].content !== message.content
						? { originalContent: history.messages[message.id].content }
						: {}),
					...message
				};
			}
		}

		if ($chatId == chatId) {
			if (!$temporaryChatEnabled) {
				const currentMessages = createMessagesList(history, history.currentId);
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: currentMessages,
					history: history,
					params: params,
					files: chatFiles
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const getChatEventEmitter = async (modelId: string, chatId: string = '') => {
		return setInterval(() => {
			$socket?.emit('usage', {
				action: 'chat',
				model: modelId,
				chat_id: chatId
			});
		}, 1000);
	};

	/**
	 * LLM 响应事件处理器（chat:completion）
	 * ========================================
	 * 处理后端通过 WebSocket 推送的 chat:completion 事件
	 * 这是前端接收 LLM 响应的核心入口，负责解析并渲染 AI 回复内容
	 *
	 * 【调用链路】
	 *   chatEventHandler (type === 'chat:completion')
	 *       ↓
	 *   chatCompletionEventHandler (本函数)
	 *       ↓
	 *   更新 message.content → 触发 UI 渲染
	 *       ↓
	 *   (done=true 时) chatCompletedHandler → 持久化
	 *
	 * 【数据来源 - 后端推送位置】
	 *   - 非流式完整响应：backend/open_webui/utils/middleware.py:2262-2282
	 *   - 流式增量 delta：backend/open_webui/utils/middleware.py:3055-3060
	 *   - 流式 usage 信息：backend/open_webui/utils/middleware.py:3128-3135
	 *   - 流式结束 done：backend/open_webui/utils/middleware.py:3823-3828
	 *
	 * 【处理流程】
	 *   1. 错误检查：如果 data.error 存在，调用 handleOpenAIError 处理
	 *   2. 引用源设置：首次收到 sources 时设置到 message.sources
	 *   3. 内容更新：
	 *      - choices 模式（OpenAI 兼容格式）：
	 *        · 非流式：choices[0].message.content（完整内容追加）
	 *        · 流式：choices[0].delta.content（增量内容追加）
	 *      - content 模式（REALTIME_CHAT_SAVE 关闭时）：
	 *        · 后端流结束后一次性返回完整内容，直接覆盖
	 *   4. Arena 模式：设置 selected_model_id 和 arena 标记
	 *   5. Token 统计：记录 usage 信息（prompt_tokens, completion_tokens）
	 *   6. 流结束处理（done=true）：
	 *      - 标记 message.done = true
	 *      - 自动复制到剪贴板（如启用）
	 *      - 自动播放 TTS（如启用）
	 *      - 派发 chat:finish 事件
	 *      - 调用 chatCompletedHandler 触发后处理和持久化
	 *
	 * @param data - 事件数据对象
	 *   @param data.id - 消息 ID（与 message.id 对应）
	 *   @param data.done - 是否完成（true 表示流式响应结束）
	 *   @param data.choices - OpenAI 格式响应数组
	 *     - choices[0].message.content：非流式完整内容
	 *     - choices[0].delta.content：流式增量内容
	 *   @param data.content - 完整内容（REALTIME_CHAT_SAVE=false 时使用）
	 *   @param data.sources - RAG 检索的引用源数组
	 *   @param data.selected_model_id - Arena 模式选中的模型 ID
	 *   @param data.error - 错误信息对象
	 *   @param data.usage - Token 使用量 { prompt_tokens, completion_tokens, total_tokens }
	 * @param message - 当前消息对象（history.messages[message_id]）
	 * @param chatId - 聊天 ID
	 */
	const chatCompletionEventHandler = async (data, message, chatId) => {
		const { id, done, choices, content, sources, selected_model_id, error, usage } = data;

		// ========== 错误处理 ==========
		if (error) {
			// --- 生命周期追踪：响应错误（completion_error 类型）---
			sendingRequestManagement.failRequest(
				message.id,
				{ errorType: 'completion_error', error: error },
				'error'
			);

			await handleOpenAIError(error, message);
		}

		// ========== 引用源初始化 ==========
		// 只在消息首次接收 sources 时设置
		if (sources && !message?.sources) {
			message.sources = sources;
		}

		// ========== 内容更新（choices 模式）==========
		// OpenAI 兼容格式：通过 choices 数组传递内容
		if (choices) {
			if (choices[0]?.message?.content) {
				// 非流式响应：choices[0].message.content 包含完整内容
				// Non-stream response
				const wasEmpty = message.content === '';
				message.content += choices[0]?.message?.content;
				if (wasEmpty && message.content !== '') {
					sendingRequestManagement.receiveFirstToken(message.id);
				}
			} else {
				// 流式响应：choices[0].delta.content 包含增量内容
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				if (message.content == '' && value == '\n') {
					console.log('Empty response');
				} else {
					// 检测首个 token（用于生命周期追踪）
					const wasEmpty = message.content === '';
					message.content += value;
					if (wasEmpty && message.content !== '') {
						sendingRequestManagement.receiveFirstToken(message.id);
					}

					// 触觉反馈（移动端）
					if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}

					// TTS 实时朗读：按句子分割，逐句派发事件
					// Emit chat event for TTS
					const messageContentParts = getMessageContentParts(
						removeAllDetails(message.content),
						$config?.audio?.tts?.split_on ?? 'punctuation'
					);
					messageContentParts.pop();

					// dispatch only last sentence and make sure it hasn't been dispatched before
					if (
						messageContentParts.length > 0 &&
						messageContentParts[messageContentParts.length - 1] !== message.lastSentence
					) {
						message.lastSentence = messageContentParts[messageContentParts.length - 1];
						eventTarget.dispatchEvent(
							new CustomEvent('chat', {
								detail: {
									id: message.id,
									content: messageContentParts[messageContentParts.length - 1]
								}
							})
						);
					}
				}
			}
		}

		// ========== 内容更新（content 模式）==========
		// 当后端 REALTIME_CHAT_SAVE 关闭时，流结束后一次性返回完整内容
		if (content) {
			// REALTIME_CHAT_SAVE is disabled
			const wasEmpty = message.content === '';
			message.content = content;
			if (wasEmpty && message.content !== '') {
				sendingRequestManagement.receiveFirstToken(message.id);
			}

			if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}

			// Emit chat event for TTS
			const messageContentParts = getMessageContentParts(
				removeAllDetails(message.content),
				$config?.audio?.tts?.split_on ?? 'punctuation'
			);
			messageContentParts.pop();

			// dispatch only last sentence and make sure it hasn't been dispatched before
			if (
				messageContentParts.length > 0 &&
				messageContentParts[messageContentParts.length - 1] !== message.lastSentence
			) {
				message.lastSentence = messageContentParts[messageContentParts.length - 1];
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: {
							id: message.id,
							content: messageContentParts[messageContentParts.length - 1]
						}
					})
				);
			}
		}

		// ========== Arena 模式 ==========
		// 后端选择了特定模型（用于模型对比/评估）
		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
			message.arena = true;
		}

		// ========== Token 使用量 ==========
		if (usage) {
			message.usage = usage;
		}

		// 更新 history 中的消息（每次收到事件都更新，触发 Svelte 响应式渲染）
		history.messages[message.id] = message;

		// ========== 流式结束处理 ==========
		// done=true 表示 LLM 响应完成，需要执行收尾逻辑
		if (done) {
			// 标记消息完成状态（UI 会根据此状态显示/隐藏加载指示器）
			message.done = true;

			// --- 自动复制功能 ---
			// 用户设置：响应完成后自动复制内容到剪贴板
			if ($settings.responseAutoCopy) {
				copyToClipboard(message.content);
			}

			// --- 自动播放 TTS ---
			// 用户设置：响应完成后自动朗读（排除通话覆盖层场景）
			if ($settings.responseAutoPlayback && !$showCallOverlay) {
				await tick();
				document.getElementById(`speak-button-${message.id}`)?.click();
			}

			// --- TTS 最后一句派发 ---
			// 确保最后一个句子片段也被派发给 TTS 引擎
			// Emit chat event for TTS
			let lastMessageContentPart =
				getMessageContentParts(
					removeAllDetails(message.content),
					$config?.audio?.tts?.split_on ?? 'punctuation'
				)?.at(-1) ?? '';
			if (lastMessageContentPart) {
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: { id: message.id, content: lastMessageContentPart }
					})
				);
			}

			// --- 派发 chat:finish 事件 ---
			// 通知其他监听者（如 TTS 控制器）响应已完成
			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			// 最终更新 history
			history.messages[message.id] = message;

			// 滚动到底部
			await tick();
			if (autoScroll) {
				scrollToBottom();
			}

			// --- 调用完成后处理器 ---
			// 触发后端 /api/chat/completed 接口，执行 Filter outlet、持久化等
			await chatCompletedHandler(
				chatId,
				message.model,
				message.id,
				createMessagesList(history, message.id)
			);

			// --- 生命周期追踪：完成请求 ---
			sendingRequestManagement.completeRequest(message.id, {
				responseLength: message.content?.length ?? 0,
				usage: message.usage ?? null,
				hasSources: (message.sources?.length ?? 0) > 0,
				sourceCount: message.sources?.length ?? 0,
				isArenaMode: message.arena ?? false,
				selectedModelId: message.selectedModelId
			});
		}

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	/**
	 * 提交用户消息 - 前端聊天流程的核心入口函数
	 *
	 * 这是用户发送消息时调用的主函数，负责：
	 * 1. 校验用户输入（prompt、模型选择、文件状态）
	 * 2. 创建用户消息对象并更新本地聊天历史
	 * 3. 处理文件附件（图片、文档等）
	 * 4. 调用 sendMessage 发起 API 请求
	 * 
	 *   1. 模型验证 (1511-1520)
			- 检查选中模型是否仍然存在
			- 过滤掉已删除的模型，避免请求失败
		2. 输入验证 (1522-1558)
			- 检查是否输入了内容或上传了文件
			- 检查是否选择了模型
			- 检查文件上传状态（非图片文件需等待上传完成）
			- 检查文件数量限制（防止请求过大）
		3. 聊天状态检查 (1560-1576)
			- 检查上一条消息是否已完成（防止重复提交）
			- 检查上一条消息是否有错误
		4. 清空输入框 (1578-1580)
			- 清空输入框内容
			- 重置 prompt 变量
		5. 处理文件附件 (1582-1603)
			- 深拷贝文件列表
			- 将文档类文件添加到聊天上下文（用于 RAG 检索）
			- 去重防止重复添加
			- 清空当前输入的文件列表
		6. 创建用户消息对象 (1605-1616)
			- 生成唯一消息 ID (UUID)
			- 构造消息对象：id、parentId、childrenIds、role、content、files、timestamp、models
		7. 更新本地聊天历史 (1618-1629)
			- 将用户消息添加到 history.messages
			- 设置 history.currentId 为当前消息 ID
			- 更新父消息的 childrenIds（构建消息树，支持对话分支）
		8. UI 操作 (1631-1637)
			- 重新聚焦输入框
			- 保存选中的模型到 sessionStorage（用于页面刷新恢复）
		9. 发送消息到后端 (1639-1641)
			- 调用 sendMessage(history, userMessageId, { newChat: true })
			- newChat: true 表示如果是新对话的第一条消息，需先创建聊天记录
	 *
	 * @param userPrompt - 用户输入的文本内容
	 * @param _raw - 是否使用原始格式（当前未使用）
	 */
	const submitPrompt = async (userPrompt, { _raw = false } = {}) => {
		console.log('submitPrompt', userPrompt, $chatId);

		// === 1. 模型验证：确保选中的模型仍然存在 ===
		// 过滤掉已被删除或不可用的模型，避免发送请求时出错
		const _selectedModels = selectedModels.map((modelId) => {
			const allIds = [...$models.map((m) => m.id), ...$userModels.map((m) => m.id)];
			return allIds.includes(modelId) ? modelId : '';
		});

		// 如果模型列表发生变化，同步更新
		if (JSON.stringify(selectedModels) !== JSON.stringify(_selectedModels)) {
			selectedModels = _selectedModels;
		}

		// === 2. 输入验证 ===
		// 2.1 检查是否输入了内容或上传了文件
		if (userPrompt === '' && files.length === 0) {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}

		// 2.2 检查是否选择了模型
		if (selectedModels.includes('')) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		// 2.3 检查文件上传状态（非图片文件需要等待上传完成）
		// 图片文件可以立即发送，因为支持本地 base64 编码
		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}

		// 2.4 检查文件数量限制（防止用户上传过多文件导致请求过大）
		if (
			($config?.file?.max_count ?? null) !== null &&
			files.length + chatFiles.length > $config?.file?.max_count
		) {
			toast.error(
				$i18n.t(`You can only chat with a maximum of {{maxCount}} file(s) at a time.`, {
					maxCount: $config?.file?.max_count
				})
			);
			return;
		}

		// === 3. 检查当前聊天状态 ===
		if (history?.currentId) {
			const lastMessage = history.messages[history.currentId];

			// 3.1 如果上一条消息还没完成（正在生成中），禁止提交新消息
			if (lastMessage.done != true) {
				// Response not done
				return;
			}

			// 3.2 错误消息已在 chatEventHandler 中删除，此处无需处理，直接继续
		}

		// === 4. 清空输入框 ===
		messageInput?.setText('');
		prompt = '';

		// === 5. 处理文件附件 ===
		const messages = createMessagesList(history, history.currentId);
		const _files = JSON.parse(JSON.stringify(files)); // 深拷贝文件列表

		// 5.1 将当前消息的文档类文件添加到聊天上下文文件列表
		// 这些文件将在整个对话中保持可用（用于 RAG 检索等）
		chatFiles.push(
			..._files.filter((item) =>
				['doc', 'text', 'file', 'note', 'chat', 'folder', 'collection'].includes(item.type)
			)
		);

		// 5.2 去重：防止同一文件被多次添加到上下文
		chatFiles = chatFiles.filter(
			// Remove duplicates
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		// 5.3 清空当前输入的文件列表（已保存到 _files 和 chatFiles）
		files = [];
		// 移动端不自动聚焦
		messageInput?.setText('', undefined, { focusInput: !isMobileDevice() });

		// === 6. 创建用户消息对象 ===
		let userMessageId = uuidv4(); // 生成唯一消息 ID
		let userMessage = {
			id: userMessageId,
			parentId: messages.length !== 0 ? messages.at(-1).id : null, // 链接到父消息（上一条消息）
			childrenIds: [], // 初始化子消息列表（用于分支对话）
			role: 'user',
			content: userPrompt,
			files: _files.length > 0 ? _files : undefined, // 附加文件（图片、文档等）
			timestamp: Math.floor(Date.now() / 1000), // Unix 时间戳
			models: selectedModels // 记录使用的模型（用于多模型对话）
		};

		console.debug('[chat] send user message', {
			chatId: $chatId,
			messageId: userMessageId,
			contentPreview: userPrompt.slice(0, 200),
			files: _files?.map((f) => f.name ?? f.id) ?? []
		});

		// 锁定记忆开关：首条用户消息创建后不再允许切换
		memoryLocked = true;

		// === 7. 更新本地聊天历史 ===
		// 7.1 将用户消息添加到历史记录
		history.messages[userMessageId] = userMessage;

		// 7.2 设置当前消息 ID（用于定位当前对话位置）
		history.currentId = userMessageId;

		// 7.3 更新父消息的子消息列表（构建消息树结构）
		// 这种树状结构支持对话分支（用户可以回到之前的消息重新生成响应）
		if (messages.length !== 0) {
			history.messages[messages.at(-1).id].childrenIds.push(userMessageId);
		}

		// === 8. UI 操作 ===
		// 重新聚焦输入框，方便用户继续输入
		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		// 保存当前选中的模型到 sessionStorage（用于刷新页面后恢复）
		saveSessionSelectedModels();

		// === 9. 发送消息到后端 ===
		// newChat: true 表示如果是新对话的第一条消息，需要先创建聊天记录
		// submitAt: 记录用户点击发送的时间，用于生命周期埋点
		const submitAt = Date.now();
		await sendMessage(history, userMessageId, { newChat: true, submitAt });
	};

	/**
	 * 发送消息到后端 - 创建响应消息并调用 API
	 *
	 * 这是聊天消息发送的核心函数，负责：
	 * 1. 为每个选中的模型创建空的响应消息占位符
	 * 2. 如果是新对话的第一条消息，先创建聊天记录
	 * 3. 并发向所有选中的模型发送请求（支持多模型对话）
	 * 4. 更新聊天列表
	 * 
	 *   1. UI 自动滚动 (1708-1711)
			- 如果启用了自动滚动，滚动到底部
		 2. 深拷贝数据 (1713-1715)
		 	- 深拷贝 chatId 和 history，避免状态污染
		 3. 确定模型列表 (1717-1724)
		 	- 优先级：指定的 modelId > atSelectedModel（@ 选择的模型）> selectedModels（全局选择）
		 4. 创建响应消息占位符 (1726-1765)
		 	- 为每个选中的模型创建空的响应消息对象
		 	- 初始 content 为空，后续通过 WebSocket 流式填充
		 	- 将响应消息添加到 history.messages
		 	- 更新父消息的 childrenIds（构建消息树）
		 	- 记录 responseMessageId（key 格式：modelId-modelIdx）
		 5. 创建聊天记录 (1767-1771)
		 	- 如果是新对话的第一条消息（newChat=true 且 parentId=null）
		 	- 调用 initChatHandler 创建聊天记录并获取 chatId
		 6. 保存聊天历史 (1775-1778)
		 	- 调用 saveChatHandler 将消息树保存到数据库
		 7. 并发发送请求 (1780-1832)
		 	- 使用 Promise.all 并行向所有选中的模型发送请求
		 	- 对每个模型：
		 		- 7.1 检查模型视觉能力（如果消息包含图片）
		 	- 7.2 获取响应消息 ID
		 	- 7.3 启动聊天事件发射器（定时发送心跳，用于统计模型使用）
		 	- 7.4 调用 sendMessageSocket 发送 API 请求
		 	- 7.5 清理事件发射器
		 8. 更新聊天列表 (1834-1836)
		 	- 刷新侧边栏聊天列表
			
	 * @param _history - 聊天历史对象（消息树）
	 * @param parentId - 父消息 ID（用户消息 ID）
	 * @param messages - 可选的自定义消息列表（用于重新生成等场景）
	 * @param modelId - 可选的指定模型 ID（用于单模型重新生成）
	 * @param modelIdx - 可选的模型索引（用于多模型对话中的特定模型）
	 * @param newChat - 是否是新对话的第一条消息
	 */
	const sendMessage = async (
		_history,
		parentId: string,
		{
			messages = null,
			modelId = null,
			modelIdx = null,
			newChat = false,
			submitAt = Date.now()
		}: {
			messages?: any[] | null;
			modelId?: string | null;
			modelIdx?: number | null;
			newChat?: boolean;
			submitAt?: number;
		} = {}
	) => {
		// === 1. UI 自动滚动 ===
		if (autoScroll) {
			scrollToBottom();
		}

		// === 2. 深拷贝数据，避免状态污染 ===
		let _chatId = JSON.parse(JSON.stringify($chatId));
		_history = JSON.parse(JSON.stringify(_history));

		// === 3. 确定要使用的模型列表 ===
		const responseMessageIds: Record<PropertyKey, string> = {};
		// 优先级：指定的 modelId > atSelectedModel（@ 选择的模型）> selectedModels（全局选择）
		let selectedModelIds = modelId
			? [modelId]
			: atSelectedModel !== undefined
				? [atSelectedModel.id]
				: selectedModels;

		// === 4. 准备用户消息数据（用于生命周期追踪）===
		const userMessage = _history.messages[parentId];
		const chatContextForTracking = chat ? parseChatForTracking(chat) : null;
		const featuresForTracking = getFeatures();

		// === 5. 为每个选中的模型创建响应消息占位符 ===
		// 这样 UI 可以立即显示"正在输入..."状态
		for (const [_modelIdx, modelId] of selectedModelIds.entries()) {
			const combined = getCombinedModelById(modelId);
			if (combined) {
				const model = combined.model ?? combined.credential;
				// 5.1 生成响应消息 ID 和空消息对象
				let responseMessageId = uuidv4();
				let responseMessage = {
					parentId: parentId,
					id: responseMessageId,
					childrenIds: [],
					role: 'assistant',
					content: '', // 初始为空，后续通过 WebSocket 流式填充
					model:
						combined.source === 'user' && combined.credential
							? combined.credential.model_id
							: model.id,
					modelName:
						// Priority 1: Custom name for this session
						customModelNames[modelId] ||
						// Priority 2: User credential name or platform model name
						(combined.source === 'user' && combined.credential
							? (combined.credential.name ?? combined.credential.model_id)
							: (model.name ?? model.id)),
					modelIdx: modelIdx ? modelIdx : _modelIdx, // 多模型对话时，区分不同模型的响应
					timestamp: Math.floor(Date.now() / 1000), // Unix epoch
					is_user_model: combined.source === 'user' // 是否为用户私有 API 模型
				};

				// 5.2 将响应消息添加到历史记录
				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// 5.3 更新父消息（用户消息）的子消息列表
				// 构建消息树：user message -> [assistant message 1, assistant message 2, ...]
				if (parentId !== null && history.messages[parentId]) {
					// Add null check before accessing childrenIds
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
				}

				// 5.4 记录响应消息 ID，用于后续查找
				// key 格式：modelId-modelIdx，例如 "gpt-4-0"
				responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`] = responseMessageId;

				// 5.5 启动请求生命周期追踪（在创建响应消息后立即调用，确保时间戳准确）
				// 从配置获取超时时间（秒），默认 30 秒
				const timeoutSeconds = $config?.ui?.request_timeout_seconds ?? 30;
				sendingRequestManagement.startRequest(responseMessageId, {
					isNewChat: newChat && userMessage?.parentId === null,
					chatId: _chatId,
					userMessageId: parentId,
					messageLength: userMessage?.content?.length ?? 0,
					modelId: modelId,
					modelName: model.name ?? model.id ?? modelId,
					isUserModel: combined.source === 'user',
					provider: extractProvider(combined),
					responseMessageId: responseMessageId,
					chatContext: chatContextForTracking,
					hasFiles: (userMessage?.files?.length ?? 0) > 0,
					fileCount: userMessage?.files?.length ?? 0,
					selectedTools: selectedToolIds,
					features: featuresForTracking
				}, submitAt, timeoutSeconds);
			}
		}
		history = history;

		// === 5. 如果是新对话的第一条消息，先创建聊天记录 ===
		// 检查条件：newChat=true 且当前消息没有父消息（说明是第一条用户消息）
		if (newChat && _history.messages[_history.currentId].parentId === null) {
			_chatId = await initChatHandler(_history);
		}

		await tick();

		// === 6. 保存聊天历史到数据库 ===
		_history = JSON.parse(JSON.stringify(history));
		// Save chat after all messages have been created
		await saveChatHandler(_chatId, _history);

		// === 7. 并发向所有选中的模型发送请求 ===
		// 使用 Promise.all 实现并行请求，提升多模型对话的性能
		await Promise.all(
			selectedModelIds.map(async (modelId, _modelIdx) => {
				// console.log('modelId', modelId);
				const combined = getCombinedModelById(modelId);
				const model = combined?.model ?? combined?.credential;

				if (combined && model) {
					// 7.1 检查模型视觉能力（如果消息包含图片）
					const hasImages = createMessagesList(_history, parentId).some((message) =>
						message.files?.some((file) => file.type === 'image')
					);

					// 如果消息包含图片，但模型不支持视觉，提示错误（私有模型默认视为支持）
					if (
						combined.source !== 'user' &&
						hasImages &&
						!(model.info?.meta?.capabilities?.vision ?? true)
					) {
						toast.error(
							$i18n.t('Model {{modelName}} is not vision capable', {
								modelName: model.name ?? model.id
							})
						);
					}

					// 7.2 获取响应消息 ID
					let responseMessageId =
						responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`];

					// 7.3 启动聊天事件发射器（定时向后端发送心跳，用于统计模型使用情况）
					const chatEventEmitter = await getChatEventEmitter(model.id, _chatId);

					scrollToBottom();

					// 7.4 发送 API 请求（核心函数）
					// sendMessageSocket 负责：
					// - 构造请求 payload（messages、files、tools、features 等）
					// - 调用 generateOpenAIChatCompletion API
					// - 处理流式响应（通过 WebSocket 实时更新消息内容）
					await sendMessageSocket(
						combined,
						messages && messages.length > 0
							? messages // 使用自定义消息列表（例如重新生成时追加 follow-up）
							: createMessagesList(_history, responseMessageId), // 使用完整历史记录
						_history,
						responseMessageId,
						_chatId
					);

					// 7.5 清理事件发射器
					if (chatEventEmitter) clearInterval(chatEventEmitter);
				} else {
					toast.error($i18n.t(`Model {{modelId}} not found`, { modelId }));
				}
			})
		);

		// === 8. 更新聊天列表（刷新侧边栏）===
		currentChatPage.set(1);
		chats.set(await getChatList(localStorage.token, $currentChatPage));
	};

	const getFeatures = () => {
		let features = {};

		if ($config?.features)
			features = {
				image_generation:
					$config?.features?.enable_image_generation &&
					($user?.role === 'admin' || $user?.permissions?.features?.image_generation)
						? imageGenerationEnabled
						: false,
				code_interpreter:
					$config?.features?.enable_code_interpreter &&
					($user?.role === 'admin' || $user?.permissions?.features?.code_interpreter)
						? codeInterpreterEnabled
						: false,
				web_search:
					$config?.features?.enable_web_search &&
					($user?.role === 'admin' || $user?.permissions?.features?.web_search)
						? webSearchEnabled
						: false
			};

		const currentModels = atSelectedModel?.id ? [atSelectedModel.id] : selectedModels;
		if (
			currentModels.filter(
				(model) => $models.find((m) => m.id === model)?.info?.meta?.capabilities?.web_search ?? true
			).length === currentModels.length
		) {
			if ($config?.features?.enable_web_search && ($settings?.webSearch ?? false) === 'always') {
				features = { ...features, web_search: true };
			}
		}

		if ($settings?.memory ?? false) {
			features = { ...features, memory: true };
		}

		// 如果用户手动切换了记忆开关,覆盖全局设置
		if (memoryEnabled !== undefined && memoryEnabled !== ($settings?.memory ?? false)) {
			features = { ...features, memory: memoryEnabled };
		}

		return features;
	};

	const getCombinedModelById = (modelId) => {
		const platform = $models.find((m) => m.id === modelId);
		if (platform) return { source: 'platform', model: platform };
		const priv = $userModels.find((m) => m.id === modelId);
		if (priv) return { source: 'user', credential: priv };
		return null;
	};

	/**
	 * 从模型对象中提取 provider 标识
	 *
	 * @param combined - getCombinedModelById 返回的组合对象
	 * @returns provider 字符串，如果无法确定则返回 null
	 *
	 * 提取规则：
	 * - 系统模型：优先使用 model.info?.provider，回退到 model.owned_by
	 * - 用户模型：从 credential.base_url 提取域名
	 */
	const extractProvider = (combined: { source: string; model?: any; credential?: any } | null): string | null => {
		if (!combined) return null;

		if (combined.source === 'platform' && combined.model) {
			const model = combined.model;
			if (model.info?.provider) {
				return model.info.provider;
			}
			if (model.owned_by) {
				return model.owned_by;
			}
			return null;
		}

		if (combined.source === 'user' && combined.credential) {
			const baseUrl = combined.credential.base_url;
			if (!baseUrl || typeof baseUrl !== 'string') {
				return null;
			}

			try {
				const url = new URL(baseUrl);
				return url.hostname;
			} catch (error) {
				console.warn('Invalid base_url format:', baseUrl, error);
				const cleaned = baseUrl.replace(/^https?:\/\//, '').split('/')[0];
				return cleaned || null;
			}
		}

		return null;
	};

	/**
	 * sendMessageSocket - 通过 WebSocket 向 LLM 发送对话请求
	 *
	 * 【调用链路】
	 *
	 *   用户发送消息
	 *        ↓
	 *   submitPrompt() (构建用户消息和空的助手消息)
	 *        ↓
	 *   ┌─────────────────────────────────────────────────────────────────────┐
	 *   │  sendMessageSocket() ← 当前函数                                      │
	 *   │    ├── 准备文件列表 (chatFiles + userMessage.files)                  │
	 *   │    ├── 格式化消息数组 (添加 system prompt, 处理图片)                  │
	 *   │    ├── 提取工具配置 (toolIds + toolServerIds)                        │
	 *   │    ├── 调用 generateOpenAIChatCompletion() API                       │
	 *   │    └── 注册 task_id 到 taskIds 数组                                  │
	 *   └─────────────────────────────────────────────────────────────────────┘
	 *        ↓
	 *   后端 POST /api/chat/completions
	 *        ↓
	 *   后端通过 Socket.IO 推送 chat:completion 事件
	 *        ↓
	 *   chatEventHandler() → chatCompletionEventHandler() 处理流式响应
	 *
	 * 【后端代码位置】
	 *
	 *   • API 入口: backend/open_webui/routers/openai.py
	 *     - generate_openai_chat_completion() 函数
	 *   • 中间件处理: backend/open_webui/utils/middleware.py
	 *     - chat_completion_filter_functions_handler() - Filter 管道
	 *     - chat_completion_tools_and_web_search_handler() - 工具调用
	 *   • 流式响应: backend/open_webui/utils/response.py
	 *     - generate_chat_completion() - 创建 SSE 流
	 *
	 * 【请求体结构】(发送给 /api/chat/completions)
	 *
	 *   {
	 *     stream: true,                    // 启用流式响应
	 *     model: "gpt-4",                  // 模型 ID
	 *     messages: [                      // OpenAI 格式的消息数组
	 *       { role: "system", content: "..." },
	 *       { role: "user", content: "..." | [...] },  // 可能包含图片
	 *       { role: "assistant", content: "..." }
	 *     ],
	 *     params: { temperature, top_p, ... },  // 模型参数
	 *     files: [...],                    // RAG 检索用的文件列表
	 *     tool_ids: ["tool1", "tool2"],    // 启用的工具 ID
	 *     tool_servers: [...],             // 外部工具服务器配置
	 *     session_id: "socket-id",         // Socket.IO 会话 ID (用于推送响应)
	 *     chat_id: "chat-uuid",            // 对话 ID
	 *     id: "response-msg-id",           // 响应消息 ID
	 *     background_tasks: {              // 后台任务配置
	 *       title_generation: true,        // 自动生成标题
	 *       tags_generation: true,         // 自动生成标签
	 *       follow_up_generation: true     // 自动生成跟进问题
	 *     }
	 *   }
	 *
	 * 【错误处理策略】
	 *
	 *   API 调用失败时:
	 *   1. 显示 toast 错误提示
	 *   2. 从 history 中删除空的响应消息
	 *   3. 从父消息的 childrenIds 中移除引用
	 *   4. 重置 currentId 到父消息
	 *   5. 设置父消息 done=true (恢复按钮状态)
	 *   6. 保存更新后的 history 到数据库
	 *
	 * @param {Object} combinedModel - 组合模型对象，包含 model/credential/source 等信息
	 * @param {Array} _messages - 要发送的消息数组 (已处理的对话历史)
	 * @param {Object} _history - 完整的消息历史对象 { messages: {}, currentId }
	 * @param {string} responseMessageId - 预创建的响应消息 ID
	 * @param {string} _chatId - 对话 ID
	 */
	const sendMessageSocket = async (
		combinedModel,
		_messages,
		_history,
		responseMessageId,
		_chatId
	) => {
		// 第一步: 从历史记录中获取消息引用
		const responseMessage = _history.messages[responseMessageId]; // 预创建的空响应消息
		const userMessage = _history.messages[responseMessage.parentId]; // 用户发送的消息

		// 解析模型信息: 支持普通模型和用户自定义凭证模型
		const model = combinedModel?.model ?? combinedModel?.credential ?? combinedModel;

		// 第二步: 准备文件列表 (用于 RAG 检索)

		// 从所有消息中提取附带的文件引用
		const chatMessageFiles = _messages
			.filter((message) => message.files)
			.flatMap((message) => message.files);

		// 清理 chatFiles: 只保留仍在消息中引用的文件 (移除已删除消息的文件)
		chatFiles = chatFiles.filter((item) => {
			const fileExists = chatMessageFiles.some((messageFile) => messageFile.id === item.id);
			return fileExists;
		});

		// 合并文件列表: chatFiles (对话级) + userMessage.files (消息级)
		let files = JSON.parse(JSON.stringify(chatFiles));
		files.push(
			// 只包含文档类型的文件 (图片在后面单独处理)
			...(userMessage?.files ?? []).filter((item) =>
				['doc', 'text', 'file', 'note', 'chat', 'collection'].includes(item.type)
			)
		);
		// 去重: 基于 JSON 序列化比较
		files = files.filter(
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		// 第三步: 触发 UI 更新和事件
		scrollToBottom(); // 滚动到底部显示新消息
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				// 通知其他组件对话开始
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick(); // 等待 Svelte 完成 DOM 更新

		// 第四步: 获取用户位置 (可选, 用于 prompt 变量)
		let userLocation;
		if ($settings?.userLocation) {
			userLocation = await getAndUpdateUserLocation(localStorage.token).catch((err) => {
				console.error(err);
				return undefined;
			});
		}

		// 判断是否为用户自定义模型 (使用个人 API Key)
		const isUserModel = combinedModel?.source === 'user';
		const credential = combinedModel?.credential;

		console.log('[UserModel] isUserModel:', isUserModel);
		console.log('[UserModel] credential:', credential);
		if (isUserModel) {
			console.log('[UserModel] credential.id:', credential?.id);
		}

		const stream = true; // 始终使用流式响应

		// 第五步: 构建 OpenAI 格式的消息数组
		// 5.1 添加 system prompt (如果配置了的话)
		let messages = [
			params?.system || $settings.system
				? {
						role: 'system',
						content: `${params?.system ?? $settings?.system ?? ''}`
					}
				: undefined,
			// 处理消息内容中的 <details> 标签
			..._messages.map((message) => ({
				...message,
				content: processDetails(message.content)
			}))
		].filter((message) => message); // 过滤掉 undefined

		// 5.2 转换为 OpenAI API 格式
		// - 用户消息如有图片，转为 multimodal content 格式
		// - 使用 merged.content (如果有合并内容) 否则用原始 content
		messages = messages
			.map((message, idx, arr) => ({
				role: message.role,
				// 检查是否有图片需要处理 (仅用户消息)
				...((message.files?.filter((file) => file.type === 'image').length > 0 ?? false) &&
				message.role === 'user'
					? {
							// 有图片: 使用 OpenAI Vision 格式 [{ type: 'text' }, { type: 'image_url' }, ...]
							content: [
								{
									type: 'text',
									text: message?.merged?.content ?? message.content
								},
								...message.files
									.filter((file) => file.type === 'image')
									.map((file) => ({
										type: 'image_url',
										image_url: {
											url: file.url
										}
									}))
							]
						}
					: {
							// 无图片: 纯文本格式
							content: message?.merged?.content ?? message.content
						})
			}))
			// 过滤空消息 (保留用户消息，过滤空的助手消息)
			.filter((message) => message?.role === 'user' || message?.content?.trim());

		// 第六步: 解析工具配置
		const toolIds = []; // 内置工具/函数 ID 列表
		const toolServerIds = []; // 外部工具服务器 ID 列表

		for (const toolId of selectedToolIds) {
			if (toolId.startsWith('direct_server:')) {
				// 外部工具服务器: "direct_server:0" 或 "direct_server:server-name"
				let serverId = toolId.replace('direct_server:', '');
				// 检查是否为数字索引
				if (!isNaN(parseInt(serverId))) {
					toolServerIds.push(parseInt(serverId));
				} else {
					toolServerIds.push(serverId); // 字符串 ID
				}
			} else {
				// 内置工具 ID
				toolIds.push(toolId);
			}
		}

		// 第七步: 发送 API 请求
		// 调用 generateOpenAIChatCompletion() 发起 POST /api/chat/completions 请求
		// 后端收到请求后，会通过 Socket.IO 推送 chat:completion 事件
		const res = await generateOpenAIChatCompletion(
			localStorage.token,
			{
				stream: stream, // 启用流式响应
				model: isUserModel ? credential.model_id : model.id, // 模型 ID
				messages: messages, // OpenAI 格式的消息数组

				// 模型参数: temperature, top_p, max_tokens, stop 等
				params: {
					...$settings?.params, // 全局默认参数
					...params, // 对话级覆盖参数
					stop:
						// 解析 stop tokens: 逗号分隔字符串 → 数组，并解码转义字符
						(params?.stop ?? $settings?.params?.stop ?? undefined)
							? (params?.stop.split(',').map((token) => token.trim()) ?? $settings.params.stop).map(
									(str) => decodeURIComponent(JSON.parse('"' + str.replace(/\"/g, '\\"') + '"'))
								)
							: undefined
				},

				// RAG 和工具配置
				files: (files?.length ?? 0) > 0 ? files : undefined, // RAG 检索用的文件

				filter_ids: selectedFilterIds.length > 0 ? selectedFilterIds : undefined, // Filter 管道
				tool_ids: toolIds.length > 0 ? toolIds : undefined, // 内置工具
				tool_servers: ($toolServers ?? []).filter(
					// 外部工具服务器
					(server, idx) => toolServerIds.includes(idx) || toolServerIds.includes(server?.id)
				),
				features: getFeatures(), // 功能开关 (web_search 等)
				variables: {
					// prompt 模板变量
					...getPromptVariables($user?.name, $settings?.userLocation ? userLocation : undefined)
				},

				// 模型元信息
				model_item: isUserModel
					? { credential_id: credential.id } // 用户自定义模型: 传凭证 ID
					: $models.find((m) => m.id === model.id), // 系统模型: 传完整模型配置
				is_user_model: isUserModel,

				// Socket.IO 会话标识 (后端用于推送响应)
				session_id: $socket?.id, // Socket.IO 连接 ID
				chat_id: $chatId, // 对话 ID
				id: responseMessageId, // 响应消息 ID

				// 后台任务配置
				// 只有第一条消息时才触发标题/标签生成
				background_tasks: {
					...(!$temporaryChatEnabled &&
					(messages.length == 1 ||
						(messages.length == 2 &&
							messages.at(0)?.role === 'system' &&
							messages.at(1)?.role === 'user')) &&
					(selectedModels[0] === model.id || atSelectedModel !== undefined)
						? {
								title_generation: $settings?.title?.auto ?? true, // 自动生成标题
								tags_generation: $settings?.autoTags ?? true // 自动生成标签
							}
						: {}),
					follow_up_generation: $settings?.autoFollowUps ?? true // 自动生成跟进问题
				},

				// 流式响应选项: 如果模型支持 usage 统计，请求包含 token 计数
				...(stream && (model.info?.meta?.capabilities?.usage ?? false)
					? {
							stream_options: {
								include_usage: true // 在最后一个 chunk 中包含 token 统计
							}
						}
					: {})
			},
			`${WEBUI_BASE_URL}/api`
		).catch(async (error) => {
			// 检查消息是否已被用户停止
			// 如果已停止，跳过错误处理（消息已在 stopResponse 中撤销，错误对用户不重要）
			if ($stoppedMessageIds.has(responseMessageId)) {
				// 从 set 中移除，避免内存泄漏
				stoppedMessageIds.update((ids) => {
					ids.delete(responseMessageId);
					return ids;
				});
				return null;
			}

			// 错误处理: API 请求失败时的回滚逻辑
			console.log(error);

			// 埋点：记录 HTTP 请求错误
			sendingRequestManagement.failRequest(
				responseMessageId,
				{ errorType: 'http_error', error: error },
				'error'
			);

			// 提取错误信息 (支持多种错误格式)
			let errorMessage = error;
			if (error?.error?.message) {
				errorMessage = error.error.message;
			} else if (error?.message) {
				errorMessage = error.message;
			}

			// 如果错误是对象 (无法显示)，使用通用错误提示
			if (typeof errorMessage === 'object') {
				errorMessage = $i18n.t(`Uh-oh! There was an issue with the response.`);
			}

			toast.error(`${errorMessage}`); // 显示错误提示

			// 回滚步骤 1: 从父消息的 childrenIds 中移除错误响应
			const parentId = responseMessage.parentId;
			if (parentId && history.messages[parentId]) {
				history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
					(id) => id !== responseMessageId
				);
			}

			// 回滚步骤 2: 删除空的响应消息
			delete history.messages[responseMessageId];

			// 回滚步骤 3: 重置当前消息指针到父消息
			if (history.currentId === responseMessageId) {
				history.currentId = parentId;
			}

			// 回滚步骤 4: 恢复父消息状态 (显示发送按钮而非加载中)
			if (parentId && history.messages[parentId]) {
				history.messages[parentId].done = true;
			}

			// 回滚步骤 6: 保存回滚后的 history 到数据库
			await saveChatHandler($chatId, history);

			return null; // 返回 null 表示请求失败
		});

		// 第八步: 处理 API 响应
		if (res) {
			if (res.error) {
				// API 返回了错误 (HTTP 200 但 body 包含 error)
				// 埋点：记录 API 错误
				sendingRequestManagement.failRequest(
					responseMessage.id,
					{ errorType: 'api_error', error: res.error },
					'error'
				);
				await handleOpenAIError(res.error, responseMessage);
			} 
			// 这里用于规避，在 http response 还未到达之前
			// 1. ws 就返回了错误
			// 2. 用户就点击终止回复
			else 
			{
				if (res.task_id) {
					await sendingRequestManagement.receiveHttpResponse(responseMessageId, res.task_id);
				}
				// // 成功: 注册 task_id 到 taskIds 数组
				// // 用于后续通过 chatEventHandler 匹配 Socket.IO 事件
				// if (taskIds) {
				// 	taskIds.push(res.task_id);
				// } else {
				// 	taskIds = [res.task_id];
				// }
			}
		}

		// 等待 DOM 更新并滚动到底部
		await tick();
		scrollToBottom();
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		console.error(innerError);
		if ('detail' in innerError) {
			// FastAPI error
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			// OpenAI error
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			// OpenAI error
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		// v2: 删除错误消息而不是设置 error 字段（和 chatEventHandler 一致）
		// 从 history 中删除这条错误消息
		const parentId = responseMessage.parentId;
		if (parentId && history.messages[parentId]) {
			// 从父消息的 childrenIds 中移除
			history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
				(id) => id !== responseMessage.id
			);
		}

		// 删除消息本身
		delete history.messages[responseMessage.id];

		// 如果这是当前消息，重置 currentId 到父消息
		if (history.currentId === responseMessage.id) {
			history.currentId = parentId;
		}

		// v3: 给父消息（用户消息）添加 done=true，确保按钮状态正确
		if (parentId && history.messages[parentId]) {
			history.messages[parentId].done = true;
		}

		// 保存更新后的 history 到数据库
		await saveChatHandler($chatId, history);
	};

	const stopResponse = async () => {
		// --- 生命周期追踪：用户停止响应 ---
		// 在停止之前���录当前状态并调用 stopRequest
		if (history.currentId) {
			const currentMessage = history.messages[history.currentId];
			if (currentMessage && currentMessage.role === 'assistant') {
				await sendingRequestManagement.stopRequest(
					history.currentId,
					currentMessage.content?.length ?? 0
				);
			}
		}

		if (history.currentId) {
			let last_message = history.messages[history.currentId];
			// 发现当前一条 assistant message 还没有收到第一个 token, 因此该消息可以直接撤回！
			if (last_message.role === 'assistant' && last_message.content === '') {
				const parentID = last_message.parentId;
				delete history.messages[history.currentId];
				history.currentId = parentID;
				history.messages[parentID].done = true;
				history.messages[parentID].childrenIds = [];
			}
			await saveChatHandler($chatId, history);
		}

		if (autoScroll) {
			scrollToBottom();
		}
	};

	const submitMessage = async (parentId, prompt) => {
		if (get(mobile)) {
			// Blur the input component to hide the mobile keyboard
			messageInput?.blurInput?.();
			messageInput?.dismissKeyboardHack?.();
			// Fallback: blur currently focused element
			if (typeof document !== 'undefined') {
				const active = document.activeElement;
				if (active && active instanceof HTMLElement) {
					active.blur();
				}
			}
		}
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels,
			timestamp: Math.floor(Date.now() / 1000) // Unix epoch
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		const submitAt = Date.now();
		await sendMessage(history, userMessageId, { submitAt });
	};

	const regenerateResponse = async (message, suggestionPrompt = null) => {
		// 记录用户点击重新生成的时间
		const submitAt = Date.now();

		if (history.currentId) {
			// 先删除旧的 response message，避免产生分支
			const parentId = message.parentId;
			const userMessage = history.messages[parentId];
			const isMultiModel = (userMessage?.models ?? [...selectedModels]).length > 1;

			// === 埋点：重新生成消息 ===
			trackMessageRegenerated({
				chatId: $chatId,
				userMessageId: parentId,
				oldResponseMessageId: message.id,
				oldModelId: message.model,
				oldModelName: message.modelName || message.model,
				oldIsUserModel: message.is_user_model ?? false,
				oldResponseLength: message.content?.length ?? 0,
				suggestionPrompt: suggestionPrompt,
				suggestionSource: suggestionPrompt
					? (['Add Details', 'More Concise'].includes(suggestionPrompt) ? 'preset' : 'custom')
					: null,
				isMultiModel: isMultiModel,
				modelIdx: isMultiModel ? message.modelIdx : null
			});

			if (parentId && history.messages[parentId]) {
				history.messages[parentId].childrenIds = history.messages[parentId].childrenIds.filter(
					(id) => id !== message.id
				);
			}

			delete history.messages[message.id];

			if (history.currentId === message.id) {
				history.currentId = parentId;
			}

			if (autoScroll) {
				scrollToBottom();
			}

			await sendMessage(history, userMessage.id, {
				submitAt,
				...(suggestionPrompt
					? {
							messages: [
								...createMessagesList(history, userMessage.id),
								{
									role: 'user',
									content: suggestionPrompt
								}
							]
						}
					: {}),
				...(isMultiModel
					? {
							// If multiple models are selected, use the model from the message
							modelId: message.model,
							modelIdx: message.modelIdx
						}
					: {})
			});
		}
	};

	const continueResponse = async () => {
		console.log('continueResponse');
		const _chatId = JSON.parse(JSON.stringify($chatId));

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = $models
				.filter((m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model))
				.at(0);

			if (model) {
				await sendMessageSocket(
					model,
					createMessagesList(history, responseMessage.id),
					history,
					responseMessage.id,
					_chatId
				);
			}
		}
	};

	const initChatHandler = async (history) => {
		let _chatId = $chatId;

		if (!$temporaryChatEnabled) {
			chat = await createNewChat(
				localStorage.token,
				{
					id: _chatId,
					title: $i18n.t('New Chat'),
					models: selectedModels,
					system: $settings.system ?? undefined,
					params: params,
					history: history,
					messages: createMessagesList(history, history.currentId),
					memory_enabled: memoryEnabled,
					tags: [],
					timestamp: Date.now()
				},
				$selectedFolder?.id
			);

			_chatId = chat.id;
			await chatId.set(_chatId);

			window.history.replaceState(history.state, '', `/c/${_chatId}`);

			await tick();

			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			currentChatPage.set(1);

			selectedFolder.set(null);
		} else {
			_chatId = `local:${$socket?.id}`; // Use socket id for temporary chat
			await chatId.set(_chatId);
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		if ($chatId == _chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					params: params,
					files: chatFiles,
					memory_enabled: memoryEnabled
				});
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const MAX_DRAFT_LENGTH = 5000;
	let saveDraftTimeout = null;

	const saveDraft = async (draft, chatId = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}

		if (draft.prompt !== null && draft.prompt.length < MAX_DRAFT_LENGTH) {
			saveDraftTimeout = setTimeout(async () => {
				await sessionStorage.setItem(
					`chat-input${chatId ? `-${chatId}` : ''}`,
					JSON.stringify(draft)
				);
			}, 500);
		} else {
			sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
		}
	};

	const clearDraft = async (chatId = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}
		await sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
	};

	const moveChatHandler = async (chatId, folderId) => {
		if (chatId && folderId) {
			const res = await updateChatFolderIdById(localStorage.token, chatId, folderId).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);

			if (res) {
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
				await pinnedChats.set(await getPinnedChatList(localStorage.token));

				toast.success($i18n.t('Chat moved successfully'));
			}
		} else {
			toast.error($i18n.t('Failed to move chat'));
		}
	};
</script>

<svelte:head>
	<title>
		{$settings.showChatTitleInTab !== false && $chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} • ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

<audio id="audioElement" src="" style="display: none;" />

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	on:confirm={(e) => {
		if (e.detail) {
			eventCallback(e.detail);
		} else {
			eventCallback(true);
		}
	}}
	on:cancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-full transition-width duration-200 ease-in-out {$showSidebar
		? '  md:max-w-[calc(100%-260px)]'
		: ' '} w-full max-w-full flex flex-col"
	id="chat-container"
>
	{#if !loading || $mobile}
		<div in:fade={{ duration: $mobile ? 0 : 50 }} class="w-full h-full flex flex-col">
			{#if $selectedFolder && $selectedFolder?.meta?.background_image_url}
				<div
					class="absolute {$showSidebar
						? 'md:max-w-[calc(100%-260px)] md:translate-x-[260px]'
						: ''} top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
					style="background-image: url({$selectedFolder?.meta?.background_image_url})  "
				/>

				<div
					class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
				/>
			{:else if $settings?.backgroundImageUrl ?? $config?.license_metadata?.background_image_url ?? null}
				<div
					class="absolute {$showSidebar
						? 'md:max-w-[calc(100%-260px)] md:translate-x-[260px]'
						: ''} top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
					style="background-image: url({$settings?.backgroundImageUrl ??
						$config?.license_metadata?.background_image_url})  "
				/>

				<div
					class="absolute top-0 left-0 w-full h-full bg-linear-to-t from-white to-white/85 dark:from-gray-900 dark:to-gray-900/90 z-0"
				/>
			{/if}

			<PaneGroup direction="horizontal" class="w-full h-full">
				<Pane defaultSize={50} minSize={30} class="h-full flex relative max-w-full flex-col">
					<Navbar
						bind:this={navbarElement}
						chat={{
							id: $chatId,
							chat: {
								title: $chatTitle,
								models: selectedModels,
								system: $settings.system ?? undefined,
								params: params,
								history: history,
								timestamp: Date.now()
							}
						}}
						{history}
						title={$chatTitle}
						bind:selectedModels
						shareEnabled={!!history.currentId}
						{initNewChat}
						archiveChatHandler={() => {}}
						{moveChatHandler}
						{customModelNames}
						onRenameModel={handleRenameModel}
						onSaveTempChat={async () => {
							try {
								if (!history?.currentId || !Object.keys(history.messages).length) {
									toast.error($i18n.t('No conversation to save'));
									return;
								}
								const messages = createMessagesList(history, history.currentId);
								const title =
									messages.find((m) => m.role === 'user')?.content ?? $i18n.t('New Chat');

								const savedChat = await createNewChat(
									localStorage.token,
									{
										id: uuidv4(),
										title: title.length > 50 ? `${title.slice(0, 50)}...` : title,
										models: selectedModels,
										history: history,
										messages: messages,
										timestamp: Date.now()
									},
									null
								);

								if (savedChat) {
									temporaryChatEnabled.set(false);
									chatId.set(savedChat.id);
									chats.set(await getChatList(localStorage.token, $currentChatPage));

									await goto(`/c/${savedChat.id}`);
									toast.success($i18n.t('Conversation saved successfully'));
								}
							} catch (error) {
								console.error('Error saving conversation:', error);
								toast.error($i18n.t('Failed to save conversation'));
							}
						}}
					/>

					<div class="flex flex-col flex-auto z-10 w-full @container overflow-auto">
						{#if ($settings?.landingPageMode === 'chat' && !$selectedFolder) || createMessagesList(history, history.currentId).length > 0}
							<div
								class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full z-10 scrollbar-hidden"
								id="messages-container"
								bind:this={messagesContainerElement}
								on:scroll={(e) => {
									autoScroll =
										messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
										messagesContainerElement.clientHeight + 5;
								}}
							>
								<div class=" h-full w-full flex flex-col">
									<Messages
										chatId={$chatId}
										bind:history
										bind:autoScroll
										bind:prompt
										setInputText={(text) => {
											messageInput?.setText(text);
										}}
										{selectedModels}
										{atSelectedModel}
										{sendMessage}
										{showMessage}
										{submitMessage}
										{continueResponse}
										{regenerateResponse}
										{chatActionHandler}
										topPadding={true}
										bottomPadding={files.length > 0}
										{customModelNames}
										{onSelect}
									/>
								</div>
							</div>

							<div class=" pb-2">
								<MessageInput
									bind:this={messageInput}
									{history}
									{isWaitingForResponse}
									{selectedModels}
									bind:files
									bind:prompt
									bind:autoScroll
									bind:selectedToolIds
									bind:selectedFilterIds
									bind:imageGenerationEnabled
									bind:codeInterpreterEnabled
									bind:webSearchEnabled
									bind:memoryEnabled
									{memoryLocked}
									bind:atSelectedModel
									bind:showCommands
									toolServers={$toolServers}
									{stopResponse}
									onChange={(data) => {
										if (!$temporaryChatEnabled) {
											saveDraft(data, $chatId);
										}
									}}
									on:upload={async (e) => {
										const { type, data } = e.detail;

										if (type === 'web') {
											await uploadWeb(data);
										} else if (type === 'youtube') {
											await uploadYoutubeTranscription(data);
										} else if (type === 'google-drive') {
											await uploadGoogleDriveFile(data);
										}
									}}
									on:submit={async (e) => {
										clearDraft();
										if (e.detail || files.length > 0) {
											await tick();

											submitPrompt(e.detail.replaceAll('\n\n', '\n'));
										}
									}}
								/>

								<!-- Perf Log 调试按钮 -->
								{#if latestPerfLog}
									<div class="flex justify-end mt-2">
										<button
											class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition"
											on:click={() => (showPerfLogModal = true)}
											aria-label="Performance Log"
											title="Performance Log"
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												class="w-5 h-5"
												viewBox="0 0 24 24"
												fill="none"
												stroke="currentColor"
												stroke-width="2"
											>
												<path d="M12 20V10M18 20V4M6 20v-4" />
											</svg>
										</button>
									</div>
								{/if}

								<div
									class="absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
								>
									<!-- {$i18n.t('LLMs can make mistakes. Verify important information.')} -->
								</div>
							</div>
						{:else}
							<div class="flex items-center h-full">
								<Placeholder
									{history}
									{selectedModels}
									bind:messageInput
									bind:files
									bind:prompt
									bind:autoScroll
									bind:selectedToolIds
									bind:selectedFilterIds
									bind:imageGenerationEnabled
									bind:codeInterpreterEnabled
									bind:webSearchEnabled
									bind:memoryEnabled
									{memoryLocked}
									bind:atSelectedModel
									bind:showCommands
									toolServers={$toolServers}
									{stopResponse}
									{onSelect}
									onChange={(data) => {
										if (!$temporaryChatEnabled) {
											saveDraft(data);
										}
									}}
									on:upload={async (e) => {
										const { type, data } = e.detail;

										if (type === 'web') {
											await uploadWeb(data);
										} else if (type === 'youtube') {
											await uploadYoutubeTranscription(data);
										}
									}}
									on:submit={async (e) => {
										clearDraft();
										if (e.detail || files.length > 0) {
											await tick();
											submitPrompt(e.detail.replaceAll('\n\n', '\n'));
										}
									}}
								/>
							</div>
						{/if}
					</div>
				</Pane>

				<ChatControls
					bind:this={controlPaneComponent}
					bind:history
					bind:chatFiles
					bind:params
					bind:files
					bind:pane={controlPane}
					chatId={$chatId}
					modelId={selectedModelIds?.at(0) ?? null}
					models={selectedModelIds.reduce((a, e, i, arr) => {
						const model = $models.find((m) => m.id === e);
						if (model) {
							return [...a, model];
						}
						return a;
					}, [])}
					{submitPrompt}
					{stopResponse}
					{showMessage}
					{eventTarget}
				/>
			</PaneGroup>
		</div>
	{:else if loading && !$mobile}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner className="size-5" />
			</div>
		</div>
	{/if}
</div>

<!-- Perf Log Modal -->
{#if showPerfLogModal}
	<Modal bind:show={showPerfLogModal} size="2xl">
		<div class="p-6">
			<div class="flex justify-between items-center mb-4">
				<h2 class="text-lg font-semibold dark:text-white">Performance Log</h2>
				<button
					class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
					on:click={() => (showPerfLogModal = false)}
				>
					<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			{#if latestPerfLog}
				<div class="space-y-4">
					<!-- 时间戳和消息 ID -->
					<div class="text-sm text-gray-500 dark:text-gray-400">
						<span>Message ID: {latestPerfLog.messageId}</span>
						<span class="ml-4">Time: {new Date(latestPerfLog.timestamp).toLocaleTimeString()}</span>
					</div>

					<!-- JSON 数据展示 -->
					<div class="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 overflow-auto max-h-[60vh]">
						<pre class="text-sm font-mono whitespace-pre-wrap break-words text-gray-800 dark:text-gray-200">{JSON.stringify(latestPerfLog.data, null, 2)}</pre>
					</div>

					<!-- 复制按钮 -->
					<button
						class="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition"
						on:click={() => {
							navigator.clipboard.writeText(JSON.stringify(latestPerfLog.data, null, 2));
							toast.success('Copied to clipboard');
						}}
					>
						Copy JSON
					</button>
				</div>
			{/if}
		</div>
	</Modal>
{/if}

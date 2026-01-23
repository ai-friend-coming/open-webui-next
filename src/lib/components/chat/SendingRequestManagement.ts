import { stopTask } from '$lib/apis';
import { get, writable, type Writable } from 'svelte/store';
import { toast } from 'svelte-sonner';
import i18next from 'i18next';
import {
	trackMessageLifecycle,
	type MessageLifecycleSentData,
	type MessageLifecycleResponseData,
	type MessageLifecycleErrorData,
	type MessageLifecycleTimestamps,
	type MessageLifecycleOutcome
} from '$lib/posthog';
import { stoppedMessageIds } from '$lib/stores';

// =====================================================
// ==================== 类型定义 ====================
// =====================================================

// 重新导出 posthog 中的类型，方便业务层使用
export type SentData = MessageLifecycleSentData;
export type ResponseData = MessageLifecycleResponseData;
export type ErrorData = MessageLifecycleErrorData;

/** 请求生命周期状态 */
export type RequestStatus =
	| 'pending' // 已发送请求，等待 HTTP 响应
	| 'http_received' // 已收到 HTTP 响应，等待第一个 token
	| 'streaming' // 正在流式接收 token
	| 'completed' // 成功完成
	| 'stopped' // 用户停止
	| 'error' // 发生错误
	| 'cancelled'; // 被取消

/** 完整的请求生命周期数据 */
export interface RequestLifecycle {
	status: RequestStatus;
	timestamps: MessageLifecycleTimestamps;
	sentData: SentData;
	responseData?: ResponseData;
	errorData?: ErrorData;
	taskId: string | null;
	partialResponseLength?: number;
	timeoutId?: ReturnType<typeof setTimeout>; // 超时定时器 ID
}

// =====================================================
// ==================== 管理类 ====================
// =====================================================

/**
 * 发送请求生命周期管理类
 *
 * 负责追踪消息请求的完整生命周期：
 * - 从 submitPrompt 开始
 * - 经过 HTTP 响应、第一个 token
 * - 到最终完成/停止/错误/取消
 *
 * 在请求结束时发送统一的 message_lifecycle 埋点事件
 */
export class SendingRequestManagement {
	/** 存储所有进行中的请求生命周期数据，key 为 response message id */
	requests: Record<string, RequestLifecycle> = {};

	/** 当前正在等待响应的请求 ID */
	currentRequestId: Writable<string | null> = writable(null);

	/** 超时事件：当请求超时时发送消息 ID */
	timeoutEvent: Writable<string | null> = writable(null);

	// =====================================================
	// ==================== 生命周期方法 ====================
	// =====================================================

	/**
	 * 开始一个新的请求
	 *
	 * 【调用时机】sendMessage 中��每个模型创建 responseMessage 之后
	 * 【功能】初始化请求生命周期数据，记录发送时间和业务数据
	 *
	 * @param messageId - 响应消息 ID
	 * @param sentData - 发送时的业务数据
	 * @param submitAt - submitPrompt 的调用时间戳
	 */
	startRequest(messageId: string, sentData: SentData, submitAt: number): void {
		this.currentRequestId.set(messageId);

		// 创建 30s 超时定时器
		const timeoutId = setTimeout(() => {
			console.log(`[Timeout] Timer triggered for message ${messageId}`);
			// 正确处理 async 函数的 Promise
			this.timeoutRequest(messageId).catch((error) => {
				console.error('Error in timeoutRequest:', error);
			});
		}, 30000);

		this.requests[messageId] = {
			status: 'pending',
			timestamps: {
				submitAt,
				sendRequestAt: Date.now()
			},
			sentData,
			taskId: null,
			timeoutId
		};
	}

	/**
	 * 收到 HTTP 响应
	 *
	 * 【调用时机】sendMessageSocket 收到 API 响应后
	 * 【功能】记录 HTTP 响应时间，保存 task_id
	 *
	 * @param messageId - 响应消息 ID
	 * @param taskId - 后端返回的任务 ID
	 */
	async receiveHttpResponse(messageId: string, taskId: string): Promise<void> {
		const currentRequestId = get(this.currentRequestId);
		const request = this.requests[messageId];

		if (!request) return;

		// 记录 HTTP 响应时间
		request.timestamps.httpResponseAt = Date.now();
		request.taskId = taskId;

		if (currentRequestId === messageId) {
			// 正在等待的请求
			if (request.status === 'pending') {
				request.status = 'http_received';
			}

			// 检查是否在等待期间被停止或出错
			if (request.status === 'stopped' || request.status === 'error') {
				await this.terminateTask(messageId);
				this.currentRequestId.set(null);
			}
		} else {
			// 不再等待的请求，直接终止
			await this.terminateTask(messageId);
		}
	}

	/**
	 * 收到第一个 token
	 *
	 * 【调用时机】chatCompletionEventHandler 中检测到 message.content 从空变为非空
	 * 【功能】记录第一个 token 到达时间，更新状态为 streaming
	 *
	 * @param messageId - 响应消息 ID
	 */
	receiveFirstToken(messageId: string): void {
		const request = this.requests[messageId];
		if (!request) return;

		// 只在首次调用时记录
		if (!request.timestamps.firstTokenAt) {
			request.timestamps.firstTokenAt = Date.now();
			request.status = 'streaming';

			// 清理超时定时器（收到第一个 token 说明请求正常）
			if (request.timeoutId) {
				clearTimeout(request.timeoutId);
				request.timeoutId = undefined;
			}
		}
	}

	/**
	 * 请求成功完成
	 *
	 * 【调用时机】chatCompletionEventHandler 收到 done=true
	 * 【功能】记录完成时间，收集响应数据，发送埋点
	 *
	 * @param messageId - 响应消息 ID
	 * @param responseData - 响应完成的数据
	 */
	completeRequest(messageId: string, responseData: ResponseData): void {
		const request = this.requests[messageId];
		if (!request) return;

		// 清理超时定时器
		if (request.timeoutId) {
			clearTimeout(request.timeoutId);
		}

		request.status = 'completed';
		request.timestamps.endAt = Date.now();
		request.responseData = responseData;

		// 发送埋点
		this.sendLifecycleEvent(messageId, 'completed');

		// 清理
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === messageId) {
			this.currentRequestId.set(null);
		}
		delete this.requests[messageId];
	}

	/**
	 * 用户停止请求
	 *
	 * 【调用时机】stopResponse 函数
	 * 【功能】记录停止时间，发送埋点，终止后端任务
	 *
	 * @param messageId - 响应消息 ID
	 * @param partialResponseLength - 停止时已收到的响应长度
	 */
	async stopRequest(messageId: string, partialResponseLength: number): Promise<void> {
		const request = this.requests[messageId];
		if (!request) return;

		// 清理超时定时器
		if (request.timeoutId) {
			clearTimeout(request.timeoutId);
		}

		// 记录已停止的消息 ID，用于全局通知过滤
		stoppedMessageIds.update((ids) => {
			ids.add(messageId);
			return ids;
		});

		// 先保存 taskId，然后立即清理请求，避免后续 cancel 事件重复触发埋点
		const taskId = request.taskId;

		request.status = 'stopped';
		request.timestamps.endAt = Date.now();
		request.partialResponseLength = partialResponseLength;

		// 发送埋点
		this.sendLifecycleEvent(messageId, 'stopped');

		// 清理（在 terminateTask 之前，防止竞态条件）
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === messageId) {
			this.currentRequestId.set(null);
		}
		delete this.requests[messageId];

		// 终止后端任务（此时请求已被删除，后续 cancel 事件不会再触发埋点）
		if (taskId) {
			await stopTask(localStorage.token, taskId).catch((error) => {
				toast.error(`${error}`);
				return null;
			});
		}
	}

	/**
	 * 请求失败（错误或取消）
	 *
	 * 【调用���机】
	 *   - chatEventHandler 收到 chat:message:error
	 *   - chatEventHandler 收到 chat:tasks:cancel
	 *   - chatCompletionEventHandler 收到 error 字段
	 * 【功能】记录错误信息，发送埋点
	 *
	 * @param messageId - 响应消息 ID
	 * @param errorData - 错误数据
	 * @param outcome - 结果类型 ('error' | 'cancelled')
	 */
	failRequest(
		messageId: string,
		errorData: ErrorData | null,
		outcome: 'error' | 'cancelled'
	): void {
		const request = this.requests[messageId];
		if (!request) return;

		// 清理超时定时器
		if (request.timeoutId) {
			clearTimeout(request.timeoutId);
		}

		request.status = outcome;
		request.timestamps.endAt = Date.now();
		if (errorData) {
			request.errorData = errorData;
		}

		// 发送埋点
		this.sendLifecycleEvent(messageId, outcome);

		// 清理
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === messageId) {
			this.currentRequestId.set(null);
		}
		delete this.requests[messageId];
	}

	// =====================================================
	// ==================== 兼容旧 API ====================
	// =====================================================

	/**
	 * 处理 WS chat:tasks:cancel 事件
	 */
	handleWsChatTasksCancel(messageId: string): void {
		this.failRequest(messageId, null, 'cancelled');
	}

	/**
	 * 处理 WS chat:message:error 事件
	 */
	handleWsChatMessageError(messageId: string, error?: any): void {
		this.failRequest(
			messageId,
			error ? { errorType: 'ws_error', error } : null,
			'error'
		);
	}

	// =====================================================
	// ==================== 内部方法 ====================
	// =====================================================

	/**
	 * 终止后端任务
	 */
	private async terminateTask(messageId: string): Promise<void> {
		const request = this.requests[messageId];
		if (!request) return;

		const taskId = request.taskId;
		if (taskId) {
			await stopTask(localStorage.token, taskId).catch((error) => {
				toast.error(`${error}`);
				return null;
			});
		}
	}

	/**
	 * 请求超时处理
	 *
	 * 【调用时机】startRequest 后 30s 内未收到第一个 token
	 * 【功能】终止后端任务，记录超时错误，发送埋点
	 *
	 * @param messageId - 响应消息 ID
	 */
	private async timeoutRequest(messageId: string): Promise<void> {
		const request = this.requests[messageId];
		if (!request) return;

		// 如果已经收到第一个 token 或已经结束，不处理超时
		if (
			request.status === 'streaming' ||
			request.status === 'completed' ||
			request.status === 'stopped' ||
			request.status === 'error' ||
			request.status === 'cancelled'
		) {
			return;
		}

		console.warn(`Request ${messageId} timed out after 30s without receiving first token`);

		// 先终止后端任务（如果有 taskId）
		if (request.taskId) {
			await this.terminateTask(messageId);
		}

		// 显示用户提示（使用 i18n）
		toast.error(
			i18next.t('Request timeout: No response received within 30 seconds, please try again')
		);

		// 【新增】发送超时事件，通知 Chat.svelte 标记消息为 broken
		this.timeoutEvent.set(messageId);

		// 调用 failRequest 记录超时错误
		this.failRequest(
			messageId,
			{
				errorType: 'timeout',
				error: 'No first token received within 30 seconds'
			},
			'error'
		);
	}

	/**
	 * 发送生命周期埋点事件
	 * 直接将原始数据传递给 trackMessageLifecycle，由 posthog 模块负责数据转换
	 */
	private sendLifecycleEvent(
		messageId: string,
		outcome: MessageLifecycleOutcome
	): void {
		const request = this.requests[messageId];
		if (!request) return;

		trackMessageLifecycle({
			outcome,
			timestamps: request.timestamps,
			sentData: request.sentData,
			responseData: request.responseData,
			errorData: request.errorData,
			partialResponseLength: request.partialResponseLength
		});
	}
}

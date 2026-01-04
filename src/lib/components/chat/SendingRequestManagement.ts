
import { stopTask } from '$lib/apis';
import { get, writable, type Writable } from 'svelte/store';
import { toast } from 'svelte-sonner';

export class SendingRequestManagement {

	requests: Record<string, { task_id: string | null; stopped: boolean; error: boolean }> = {};
	// key: 待补全的 assistant assistant 的 message_id
	// value: 
	// 	task_id: 该 request 对应的 task_id
	//  stopped: 用户放弃该 request 的标识
	// 	error: 该 request 出错的标识
	currentRequestId: Writable<string | null> = writable(null);

	sendRequest(message_id: string): void {
		this.currentRequestId.set(message_id);
		this.requests[message_id] = {
			task_id: null,
			stopped: false,
			error: false
		};
		// TODO: 设置定时器，如果三十秒后
	}

	async receiveHttpResponse(message_id: string, task_id: string): Promise<void> {
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === message_id) { // 获得了正在等待的 request message id 的 http response, 包含 task id
			const stopped = this.requests[message_id].stopped;
			const error = this.requests[message_id].error;
			if (stopped || error) {
				await this.terminiteTask(message_id);
				this.currentRequestId.set(null);
			} else {
				this.requests[message_id] = {
					...this.requests[message_id],
					task_id
				};
			}
		} else { // 获得了不再等待的 request message id 的 http response, 包含 task id
			if (this.requests[message_id]) {
				this.requests[message_id].task_id = task_id;
				await this.terminiteTask(message_id);
			}
		}
	}

	async terminiteTask(message_id: string) : Promise<void> {
		const task_id = this.requests[message_id].task_id;
		delete this.requests[message_id];
		if (task_id) {
				const res = await stopTask(localStorage.token, task_id).catch((error) => {
				toast.error(`${error}`);
				return null;
			});
		}
	}

	async stopCurrentResponse(): Promise<void> {
		const message_id = get(this.currentRequestId);
		if (message_id) {
			if (this.requests[message_id].task_id !== null) { // 如果 task_id 不为空，说明已经获得了第一个 token
				await this.terminiteTask(message_id);
			} else { // // 如果 task_id 不为空，说明还未获得 http response
				this.requests[message_id] = {
					...this.requests[message_id],
					stopped: true
				}
			}
			this.currentRequestId.set(null);
		}
	}

	handleWsChatTasksCancel(message_id: string): void {
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === message_id) {
			if (this.requests[message_id]) {
				this.requests[message_id] = {
					...this.requests[message_id],
					error: true
				};
			}
			this.currentRequestId.set(null);
		}
	}

	handleWsChatMessageError(message_id: string): void {
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === message_id) {
			if (this.requests[message_id]) {
				this.requests[message_id] = {
					...this.requests[message_id],
					error: true
				};
			}
			this.currentRequestId.set(null);
		}
	}
	
	handleWsChatCompletion(message_id: string): void {
		// chatCompletionEventHandler -> done -> chatCompletedHandler
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === message_id) {
			this.currentRequestId.set(null);
			delete this.requests[message_id];
		}
	}

	async handleWsChatCompletionError(message_id: string): Promise<void> {
		// chatCompletionEventHandler -> done -> chatCompletedHandler -> error
		const currentRequestId = get(this.currentRequestId);
		if (currentRequestId === message_id) {
			this.currentRequestId.set(null);
			delete this.requests[message_id];
		}
	}
}

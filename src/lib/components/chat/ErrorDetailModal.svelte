<script lang="ts">
	import { toast } from 'svelte-sonner';
	import Modal from '$lib/components/common/Modal.svelte';

	export let show = false;
	export let error: any = null;
	export let errorIndex: number = 0;

	const copyDebugLog = async () => {
		if (error?.debug_log) {
			try {
				await navigator.clipboard.writeText(error.debug_log);
				toast.success('已复制到剪贴板');
			} catch (err) {
				toast.error('复制失败');
			}
		}
	};
</script>

<Modal bind:show size="lg">
	<div class="px-5 py-4">
		<div class="flex justify-between items-center mb-4">
			<div class="text-lg font-semibold flex items-center gap-2">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5 text-red-500"
				>
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
						clip-rule="evenodd"
					/>
				</svg>
				错误详情 #{errorIndex + 1}
			</div>
			<button
				class="self-center"
				on:click={() => {
					show = false;
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>

		{#if error}
			<div class="space-y-4">
				<!-- 时间戳 -->
				<div>
					<div class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">时间</div>
					<div class="text-sm text-gray-900 dark:text-gray-100">
						{error.timestamp || '未知'}
					</div>
				</div>

				<!-- 用户提示消息 -->
				<div>
					<div class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">错误消息</div>
					<div
						class="text-sm text-gray-900 dark:text-gray-100 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800"
					>
						{error.user_toast_message || '未知错误'}
					</div>
				</div>

				<!-- 调试日志 -->
				{#if error.debug_log}
					<div>
						<div class="flex justify-between items-center mb-1">
							<div class="text-sm font-medium text-gray-500 dark:text-gray-400">调试日志</div>
							<button
								class="text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition flex items-center gap-1"
								on:click={copyDebugLog}
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-4 h-4"
								>
									<path
										fill-rule="evenodd"
										d="M15.988 3.012A2.25 2.25 0 0118 5.25v6.5A2.25 2.25 0 0115.75 14H13.5V7A2.5 2.5 0 0011 4.5H8.128a2.252 2.252 0 011.884-1.488A2.25 2.25 0 0112.25 1h1.5a2.25 2.25 0 012.238 2.012zM11.5 3.25a.75.75 0 01.75-.75h1.5a.75.75 0 01.75.75v.25h-3v-.25z"
										clip-rule="evenodd"
									/>
									<path
										fill-rule="evenodd"
										d="M2 7a1 1 0 011-1h8a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V7zm2 3.25a.75.75 0 01.75-.75h4.5a.75.75 0 010 1.5h-4.5a.75.75 0 01-.75-.75zm0 3.5a.75.75 0 01.75-.75h4.5a.75.75 0 010 1.5h-4.5a.75.75 0 01-.75-.75z"
										clip-rule="evenodd"
									/>
								</svg>
								复制
							</button>
						</div>
						<pre
							class="text-xs text-gray-800 dark:text-gray-200 p-3 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-x-auto max-h-[40vh] overflow-y-auto whitespace-pre-wrap break-words font-mono">{error.debug_log}</pre>
					</div>
				{/if}
			</div>
		{:else}
			<div class="text-center py-8 text-gray-500 dark:text-gray-400">无错误信息</div>
		{/if}
	</div>
</Modal>

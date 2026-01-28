<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	export let show = false;
	export let errorMessages: any[] = [];

	const dispatch = createEventDispatcher();

	const handleSelectError = (error: any, index: number) => {
		dispatch('select', { error, index });
	};

	const truncateText = (text: string, maxLength: number = 80) => {
		if (!text) return '';
		return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
	};
</script>

<Modal bind:show size="lg">
	<div class="px-5 py-4">
		<div class="flex justify-between items-center mb-4">
			<div class="text-lg font-semibold">错误列表</div>
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

		<div class="space-y-2 max-h-[60vh] overflow-y-auto">
			{#if errorMessages && errorMessages.length > 0}
				{#each errorMessages as errorItem, index}
					<button
						class="w-full text-left p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						on:click={() => handleSelectError(errorItem.error, index)}
					>
						<div class="flex items-start gap-3">
							<div class="flex-shrink-0 mt-1">
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
							</div>
							<div class="flex-1 min-w-0">
								<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
									错误 #{index + 1}
								</div>
								<div class="text-sm text-gray-600 dark:text-gray-400 truncate">
									{truncateText(errorItem.error?.user_toast_message || '未知错误')}
								</div>
								<div class="text-xs text-gray-500 dark:text-gray-500 mt-1">
									{errorItem.error?.timestamp || ''}
								</div>
							</div>
							<div class="flex-shrink-0">
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
									class="w-5 h-5 text-gray-400"
								>
									<path
										fill-rule="evenodd"
										d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
										clip-rule="evenodd"
									/>
								</svg>
							</div>
						</div>
					</button>
				{/each}
			{:else}
				<div class="text-center py-8 text-gray-500 dark:text-gray-400">暂无错误记录</div>
			{/if}
		</div>
	</div>
</Modal>

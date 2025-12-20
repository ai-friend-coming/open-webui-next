<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { mobile, showSidebar } from '$lib/stores';
	import { createUserSuggestionFeedback } from '$lib/apis/evaluations';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext('i18n');

	let content = '';
	let contact = '';
	let submitting = false;

	const reset = () => {
		content = '';
		contact = '';
	};

	const submit = async () => {
		if (submitting) return;
		const trimmed = content.trim();
		if (!trimmed) {
			toast.error($i18n.t('请填写反馈内容'));
			return;
		}
		submitting = true;
		try {
			await createUserSuggestionFeedback(localStorage.token, {
				content: trimmed,
				contact: contact.trim() || undefined
			});
			toast.success($i18n.t('反馈已提交，感谢您的建议'));
			reset();
		} catch (err) {
			const msg = typeof err === 'string' ? err : err?.detail ?? $i18n.t('提交失败，请稍后重试');
			toast.error(msg);
		} finally {
			submitting = false;
		}
	};
</script>

<svelte:head>
	<title>{$i18n.t('反馈')} | Cakumi</title>
</svelte:head>

<div
	class="flex flex-col h-screen max-h-[100dvh] flex-1 transition-width duration-200 ease-in-out w-full max-w-full {$showSidebar
		? 'md:max-w-[calc(100%-260px)]'
		: ''}"
>
	<!-- 顶部导航栏 -->
	<nav class="px-2 pt-1.5 backdrop-blur-xl w-full drag-region">
		<div class="flex items-center">
			{#if $mobile}
				<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center">
					<Tooltip
						content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
					>
						<button
							id="sidebar-toggle-button"
							class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
							on:click={() => {
								showSidebar.set(!$showSidebar);
							}}
						>
							<div class="self-center p-1.5">
								<Sidebar />
							</div>
						</button>
					</Tooltip>
				</div>
			{/if}
			<div class="ml-2 py-0.5 self-center flex items-center">
				<h1 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{$i18n.t('反馈')}
				</h1>
			</div>
		</div>
	</nav>

	<div class="flex-1 flex flex-col min-w-[320px] overflow-hidden">
		<div class="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 py-4 pb-[max(1.5rem,env(safe-area-inset-bottom))]">
			<!-- 反馈内容 -->
			<div class="flex-1 flex flex-col space-y-2 min-h-0">
				<label class="block text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('反馈内容')}
				</label>
				<textarea
					class="flex-1 w-full rounded-xl border-0 bg-gray-50 dark:bg-gray-850 p-4 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600 resize-none placeholder:text-gray-400"
					placeholder={$i18n.t('请描述您遇到的问题或建议...')}
					bind:value={content}
				/>
			</div>

			<!-- 底部区域 -->
			<div class="flex items-center gap-4 mt-4 pt-4 pb-4 md:pb-0">
				<input
					type="text"
					class="flex-1 rounded-xl border-0 bg-gray-50 dark:bg-gray-850 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-600 placeholder:text-gray-400"
					placeholder={$i18n.t('联系方式（可选）')}
					bind:value={contact}
				/>
				<button
					class="px-6 py-3 rounded-xl text-sm font-medium text-white bg-gray-900 dark:bg-white dark:text-gray-900 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition whitespace-nowrap"
					on:click={submit}
					disabled={submitting || !content.trim()}
				>
					{submitting ? $i18n.t('提交中...') : $i18n.t('提交')}
				</button>
			</div>
		</div>
	</div>
</div>

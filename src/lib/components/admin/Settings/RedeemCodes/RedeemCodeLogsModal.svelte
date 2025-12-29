<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import { getRedeemCodeLogs, getRedeemCodeStats, type RedeemCode, type RedeemLog, type RedeemCodeStats } from '$lib/apis/redeem-codes';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let show = false;
	export let code: RedeemCode;

	let loading = false;
	let logs: RedeemLog[] = [];
	let stats: RedeemCodeStats | null = null;

	// 加载日志和统计
	const loadData = async () => {
		loading = true;
		try {
			[logs, stats] = await Promise.all([
				getRedeemCodeLogs(localStorage.token, code.id),
				getRedeemCodeStats(localStorage.token, code.id)
			]);
		} catch (error) {
			toast.error(`加载失败: ${error}`);
		} finally {
			loading = false;
		}
	};

	// 格式化时间
	const formatTime = (nanoseconds: number) => {
		return dayjs(nanoseconds / 1000000).format('YYYY-MM-DD HH:mm:ss');
	};

	$: if (show && code) {
		loadData();
	}
</script>

<Modal bind:show size="lg">
	<div class="flex flex-col h-full max-h-[80vh]">
		<!-- 标题 -->
		<div class="px-6 py-4 border-b dark:border-gray-700">
			<h3 class="text-lg font-semibold text-gray-900 dark:text-white">兑换日志</h3>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
				兑换码: <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-mono">{code.code}</code>
			</p>
		</div>

		<!-- 统计卡片 -->
		{#if stats}
			<div class="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-b dark:border-gray-700">
				<div class="grid grid-cols-3 gap-4">
					<div class="text-center">
						<div class="text-2xl font-bold text-blue-600 dark:text-blue-400">¥{stats.total_amount.toFixed(2)}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">总兑换金额</div>
					</div>
					<div class="text-center">
						<div class="text-2xl font-bold text-green-600 dark:text-green-400">{stats.total_users}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">兑换用户数</div>
					</div>
					<div class="text-center">
						<div class="text-2xl font-bold text-purple-600 dark:text-purple-400">{stats.total_uses}</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">兑换次数</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- 日志列表 -->
		<div class="flex-1 overflow-y-auto px-6 py-4">
			{#if loading}
				<div class="flex items-center justify-center h-32">
					<Spinner className="size-8" />
				</div>
			{:else if logs.length === 0}
				<div class="flex flex-col items-center justify-center h-32 text-gray-400">
					<svg class="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
					</svg>
					<p class="text-sm">暂无兑换记录</p>
				</div>
			{:else}
				<div class="space-y-3">
					{#each logs as log (log.id)}
						<div class="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
							<div class="flex items-start justify-between">
								<div class="flex-1">
									<div class="flex items-center gap-2 mb-2">
										<span class="font-medium text-gray-900 dark:text-white">{log.user_name}</span>
										<span class="text-xs text-gray-500">ID: {log.user_id}</span>
									</div>
									<div class="grid grid-cols-3 gap-4 text-sm">
										<div>
											<div class="text-gray-500 dark:text-gray-400">兑换金额</div>
											<div class="font-medium text-green-600 dark:text-green-400">+¥{log.amount.toFixed(2)}</div>
										</div>
										<div>
											<div class="text-gray-500 dark:text-gray-400">兑换前余额</div>
											<div class="font-medium">¥{log.balance_before.toFixed(2)}</div>
										</div>
										<div>
											<div class="text-gray-500 dark:text-gray-400">兑换后余额</div>
											<div class="font-medium">¥{log.balance_after.toFixed(2)}</div>
										</div>
									</div>
								</div>
								<div class="text-right text-xs text-gray-500 dark:text-gray-400 ml-4">
									{formatTime(log.created_at)}
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- 底部按钮 -->
		<div class="px-6 py-4 border-t dark:border-gray-700 flex justify-end">
			<button
				type="button"
				class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				on:click={() => (show = false)}
			>
				关闭
			</button>
		</div>
	</div>
</Modal>

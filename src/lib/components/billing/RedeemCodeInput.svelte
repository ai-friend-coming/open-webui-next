<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { redeemCode } from '$lib/apis/redeem-codes';
	import { getBalance } from '$lib/apis/billing';
	import { balance } from '$lib/stores';
	import Spinner from '$lib/components/common/Spinner.svelte';

	let code = '';
	let loading = false;

	// 兑换处理
	const handleRedeem = async () => {
		if (!code.trim()) {
			toast.error('请输入兑换码');
			return;
		}

		loading = true;
		try {
			const result = await redeemCode(localStorage.token, code.trim());

			// 更新余额
			const balanceInfo = await getBalance(localStorage.token);
			balance.set(balanceInfo);

			toast.success(result.message);
			code = ''; // 清空输入
		} catch (error) {
			toast.error(`兑换失败: ${error.message || error}`);
		} finally {
			loading = false;
		}
	};

	// 回车提交
	const handleKeyPress = (e: KeyboardEvent) => {
		if (e.key === 'Enter' && !loading && code.trim()) {
			handleRedeem();
		}
	};
</script>

<div class="p-5 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm">
	<!-- 标题 -->
	<div class="flex items-center gap-2 mb-3">
		<svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<h3 class="text-lg font-semibold text-gray-900 dark:text-white">兑换码充值</h3>
	</div>

	<p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
		输入有效的兑换码即可获得余额充值，每个兑换码每个用户只能使用一次
	</p>

	<!-- 输入框和按钮 -->
	<div class="flex gap-3">
		<input
			type="text"
			bind:value={code}
			on:keypress={handleKeyPress}
			placeholder="请输入兑换码"
			disabled={loading}
			class="flex-1 px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed transition-all"
			maxlength="32"
		/>
		<button
			on:click={handleRedeem}
			disabled={loading || !code.trim()}
			class="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 whitespace-nowrap shadow-sm hover:shadow-md"
		>
			{#if loading}
				<Spinner className="size-4" />
			{/if}
			{loading ? '兑换中...' : '立即兑换'}
		</button>
	</div>

	<!-- 提示信息 -->
	<div class="mt-3 flex items-start gap-2 text-xs text-gray-500 dark:text-gray-400">
		<svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		<div>
			<p>兑换码区分大小写，请准确输入</p>
			<p class="mt-1">如遇问题，请联系管理员</p>
		</div>
	</div>
</div>

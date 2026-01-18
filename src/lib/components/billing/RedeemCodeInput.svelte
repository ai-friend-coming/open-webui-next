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

<div class="p-6 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
	<!-- 标题 -->
	<div class="flex items-center gap-2 mb-4">
		<span class="text-xl">🎫</span>
		<h3 class="text-base font-semibold text-gray-900 dark:text-white">使用兑换码</h3>
	</div>

	<!-- 输入框 -->
	<input
		type="text"
		bind:value={code}
		on:keypress={handleKeyPress}
		placeholder="请输入兑换码"
		disabled={loading}
		class="w-full px-4 py-2.5 mb-3 border border-gray-300 dark:border-gray-600 rounded-lg
			bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400
			focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
			disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
		maxlength="32"
	/>

	<!-- 按钮 -->
	<button
		on:click={handleRedeem}
		disabled={loading || !code.trim()}
		class="w-full px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium
			transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-indigo-600
			flex items-center justify-center gap-2"
	>
		{#if loading}
			<Spinner className="size-4" />
		{/if}
		{loading ? '兑换中...' : '立即兑换'}
	</button>

	<!-- 提示信息 -->
	<div class="mt-4 flex items-start gap-2 text-sm text-gray-500 dark:text-gray-400">
		<span class="text-base leading-none mt-0.5">💡</span>
		<p>每个兑换码只能使用一次</p>
	</div>
</div>

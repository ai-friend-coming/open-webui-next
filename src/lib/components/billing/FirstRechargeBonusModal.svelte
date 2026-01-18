<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Modal from '$lib/components/common/Modal.svelte';
	import { getFirstRechargeBonusConfig } from '$lib/apis/billing';
	import { user } from '$lib/stores';

	export let show = false;

	let bonusConfig: any = null;
	let loading = true;

	onMount(async () => {
		try {
			bonusConfig = await getFirstRechargeBonusConfig();
			loading = false;
		} catch (error) {
			console.error('Failed to load first recharge bonus config:', error);
			loading = false;
		}
	});

	const handleRecharge = () => {
		show = false;
		goto('/billing');
	};

	const handleDismiss = () => {
		show = false;
		// 记录用户已看过弹窗，避免重复打扰
		localStorage.setItem('firstRechargeBonusModalShown', 'true');
	};

	$: bonusRate = bonusConfig?.rate ? bonusConfig.rate.toFixed(0) : '0';
	$: maxBonus = bonusConfig?.max_amount ? bonusConfig.max_amount.toFixed(0) : '0';
</script>

<Modal bind:show size="sm">
	<div class="flex flex-col items-center p-6 text-center">
		{#if loading}
			<div class="animate-pulse">加载中...</div>
		{:else if bonusConfig?.enabled}
			<!-- 礼物图标 -->
			<div class="mb-4 text-6xl">🎁</div>

			<!-- 标题 -->
			<h2 class="mb-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
				新人专享福利
			</h2>

			<!-- 优惠说明 -->
			<div class="mb-6 space-y-2">
				<p class="text-lg font-semibold text-primary-600 dark:text-primary-400">
					首次充值送 {bonusRate}% 奖励
				</p>
				<p class="text-sm text-gray-600 dark:text-gray-400">
					充 100 元送 {(100 * bonusConfig.rate / 100).toFixed(0)} 元
				</p>
				<p class="text-xs text-gray-500 dark:text-gray-500">
					最高可获得 {maxBonus} 元奖励
				</p>
			</div>

			<!-- 特点列表 -->
			<div class="mb-6 w-full space-y-2 rounded-lg bg-gray-50 p-4 text-left dark:bg-gray-800">
				<div class="flex items-center gap-2 text-sm">
					<span class="text-green-500">✓</span>
					<span>即充即到，实时到账</span>
				</div>
				<div class="flex items-center gap-2 text-sm">
					<span class="text-green-500">✓</span>
					<span>奖励自动发放，无需申请</span>
				</div>
				<div class="flex items-center gap-2 text-sm">
					<span class="text-green-500">✓</span>
					<span>仅限首次充值，机会难得</span>
				</div>
			</div>

			<!-- 按钮组 -->
			<div class="flex w-full gap-3">
				<button
					on:click={handleDismiss}
					class="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
				>
					稍后再说
				</button>
				<button
					on:click={handleRecharge}
					class="flex-1 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600"
				>
					立即充值
				</button>
			</div>
		{/if}
	</div>
</Modal>

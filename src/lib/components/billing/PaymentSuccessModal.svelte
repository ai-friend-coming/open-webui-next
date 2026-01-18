<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let amount: number = 0;
	export let bonusAmount: number = 0; // 首充奖励金额
	export let bonusRate: number = 0; // 首充返现比例

	const close = () => {
		show = false;
	};
</script>

<Modal bind:show size="xs">
	<div class="p-6 text-center">
		<!-- 成功图标 -->
		<div
			class="w-20 h-20 mx-auto mb-4 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center"
		>
			<svg class="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
			</svg>
		</div>

		<!-- 标题 -->
		<h2 class="text-xl font-bold text-gray-900 dark:text-white mb-2">
			{$i18n.t('充值成功')}
		</h2>

		<!-- 金额 -->
		<p class="text-3xl font-bold text-green-500 mb-2">
			+¥{amount.toFixed(2)}
		</p>

		<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
			{$i18n.t('充值金额已到账')}
		</p>

		<!-- 首充奖励区域 -->
		{#if bonusAmount > 0}
			<div class="mb-6 p-4 rounded-xl bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-2 border-amber-300/60 dark:border-amber-600/60">
				<div class="flex items-center justify-center gap-2 mb-2">
					<div class="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center">
						<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
						</svg>
					</div>
					<h4 class="text-base font-bold bg-gradient-to-r from-amber-600 to-orange-600 dark:from-amber-400 dark:to-orange-400 bg-clip-text text-transparent">
						{$i18n.t('恭喜获得首充奖励！')}
					</h4>
				</div>
				<p class="text-2xl font-bold text-amber-600 dark:text-amber-400 mb-1">
					+¥{bonusAmount.toFixed(2)}
				</p>
				{#if bonusRate > 0}
					<p class="text-xs text-gray-600 dark:text-gray-400">
						{$i18n.t('返现比例：')}{bonusRate}%
					</p>
				{/if}
			</div>
		{/if}

		<!-- 按钮 -->
		<button
			on:click={close}
			class="w-full px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
		>
			{$i18n.t('确定')}
		</button>
	</div>
</Modal>

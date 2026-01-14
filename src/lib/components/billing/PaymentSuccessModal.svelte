<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let amount: number = 0;

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

		<p class="text-sm text-gray-500 dark:text-gray-400 mb-6">
			{$i18n.t('充值金额已到账')}
		</p>

		<!-- 按钮 -->
		<button
			on:click={close}
			class="w-full px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
		>
			{$i18n.t('确定')}
		</button>
	</div>
</Modal>

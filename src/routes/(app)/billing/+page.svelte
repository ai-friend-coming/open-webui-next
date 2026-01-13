<script lang="ts">
	import { dev } from '$app/environment';
	import { onMount, getContext } from 'svelte';
	import { balance, mobile, showSidebar, showMobileUserPanel, showMobileChatDrawer, user } from '$lib/stores';
	import { getBalance } from '$lib/apis/billing';
	import BalanceDisplay from '$lib/components/billing/BalanceDisplay.svelte';
	import BillingLogsTable from '$lib/components/billing/BillingLogsTable.svelte';
	import BillingStatsChart from '$lib/components/billing/BillingStatsChart.svelte';
	import LowBalanceAlert from '$lib/components/billing/LowBalanceAlert.svelte';
	import PaymentOrdersTable from '$lib/components/billing/PaymentOrdersTable.svelte';
	import RechargeCard from '$lib/components/billing/RechargeCard.svelte';
	import RedeemCodeInput from '$lib/components/billing/RedeemCodeInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	onMount(async () => {
		try {
			const balanceInfo = await getBalance(localStorage.token);
			balance.set(balanceInfo);
		} catch (error) {
			toast.error($i18n.t('加载余额失败: ') + error.message);
		}
	});
</script>

<svelte:head>
	<title>{$i18n.t('计费中心')} | Cakumi</title>
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
				<div class="flex flex-none items-center">
					<Tooltip content={$i18n.t('Menu')}>
						<button
							class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
							on:click={() => {
								showMobileUserPanel.set(true);
							}}
						>
							<div class="self-center p-1.5">
								{#if $user?.profile_image_url}
									<img
										src={$user.profile_image_url}
										class="size-6 object-cover rounded-full"
										alt=""
										draggable="false"
									/>
								{:else}
									<SidebarIcon />
								{/if}
							</div>
						</button>
					</Tooltip>
				</div>
			{/if}

			<div class="ml-2 py-0.5 self-center flex items-center justify-between w-full">
				<h1 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{$i18n.t('计费中心')}
				</h1>

				{#if $mobile}
					<div class="flex items-center gap-1">
						<Tooltip content={$i18n.t('Chats')}>
							<button
								class="cursor-pointer flex px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showMobileChatDrawer.set(true);
								}}
							>
								<svg class="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
								</svg>
							</button>
						</Tooltip>
					</div>
				{/if}
			</div>
		</div>
	</nav>

	<div class="flex-1 overflow-y-auto min-w-[320px]">
		<div class="billing-page max-w-7xl mx-auto px-4 py-4 pb-16">
			<!-- 页面副标题 -->
			<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
				{$i18n.t('查看您的余额、消费记录和统计信息')}
			</p>

			<!-- 余额不足警告 -->
			<LowBalanceAlert />

			<!-- 两栏布局：左侧自适应，右侧固定宽度 -->
			<div class="flex flex-col lg:flex-row gap-6 mt-6">
				<!-- 左侧主内容区（自适应宽度） -->
				<div class="flex-1 min-w-0 space-y-6 order-2 lg:order-1">
					<!-- 余额卡片 -->
					<BalanceDisplay />

					<!-- 统计图表 -->
					<BillingStatsChart />

					<!-- 充值记录 -->
					<PaymentOrdersTable />

					<!-- 消费记录 (仅 debug 模式显示) -->
					{#if dev}
						<BillingLogsTable />
					{/if}
				</div>

				<!-- 右侧充值卡片（固定宽度，移动端显示在上方） -->
				<div class="lg:w-[360px] lg:flex-shrink-0 order-1 lg:order-2">
					<div class="lg:sticky lg:top-6 space-y-4">
						<RechargeCard />
						<RedeemCodeInput />
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

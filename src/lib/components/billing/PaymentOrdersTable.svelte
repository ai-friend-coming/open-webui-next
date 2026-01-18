<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { getPaymentOrders, type PaymentOrder } from '$lib/apis/billing';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { toast } from 'svelte-sonner';

	const i18n = getContext('i18n');

	let orders: PaymentOrder[] = [];
	let loading = false;
	let limit = 20;
	let offset = 0;
	let hasMore = true;

	const loadOrders = async () => {
		loading = true;
		try {
			const data = await getPaymentOrders(localStorage.token, limit, offset);

			if (data.length < limit) {
				hasMore = false;
			}

			orders = [...orders, ...data];
			offset += data.length;
		} catch (error: any) {
			toast.error($i18n.t('加载充值记录失败: ') + (error.message || error));
		} finally {
			loading = false;
		}
	};

	onMount(() => {
		orders = [];
		offset = 0;
		hasMore = true;
		loadOrders();
	});

	const formatDate = (timestamp: number) => {
		const date = new Date(timestamp * 1000);
		return date.toLocaleString('zh-CN', {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	};

	const getStatusLabel = (status: string) => {
		const labels: Record<string, string> = {
			pending: '待支付',
			paid: '已支付',
			closed: '已关闭',
			refunded: '已退款'
		};
		return labels[status] || status;
	};

	const getStatusClass = (status: string) => {
		const classes: Record<string, string> = {
			pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
			paid: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
			closed: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
			refunded: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
		};
		return classes[status] || 'bg-gray-100 text-gray-600';
	};

	const copyOrderNo = (orderNo: string) => {
		navigator.clipboard.writeText(orderNo);
		toast.success($i18n.t('订单号已复制'));
	};
</script>

<div class="payment-orders-table bg-white/70 dark:bg-gray-800/70 backdrop-blur-xl rounded-2xl border border-white/30 dark:border-gray-700/50 shadow-lg hover:shadow-xl transition-all duration-300 overflow-hidden">
	<div class="table-header px-5 py-4 border-b border-gray-200/50 dark:border-gray-700/50">
		<div class="flex items-center gap-2.5">
			<div class="p-1.5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg">
				<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
				</svg>
			</div>
			<h2 class="text-lg font-semibold text-gray-900 dark:text-white">{$i18n.t('充值记录')}</h2>
		</div>
	</div>

	<div class="table-container overflow-x-auto">
		<table class="w-full">
			<thead>
				<tr class="bg-gradient-to-r from-gray-50/80 to-gray-100/80 dark:from-gray-700/50 dark:to-gray-800/50 backdrop-blur-sm">
					<th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap uppercase tracking-wider"
						>{$i18n.t('时间')}</th
					>
					<th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap uppercase tracking-wider"
						>{$i18n.t('订单号')}</th
					>
					<th class="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap uppercase tracking-wider"
						>{$i18n.t('金额')}</th
					>
					<th class="px-4 py-3 text-center text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap uppercase tracking-wider"
						>{$i18n.t('状态')}</th
					>
					<th class="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 whitespace-nowrap uppercase tracking-wider"
						>{$i18n.t('支付时间')}</th
					>
				</tr>
			</thead>
			<tbody>
				{#each orders as order (order.id)}
					<tr
						class="border-b border-gray-200/30 dark:border-gray-700/30 hover:bg-white/50 dark:hover:bg-gray-700/30 transition-colors"
					>
						<td class="px-4 py-3 text-sm text-gray-700 dark:text-gray-300 whitespace-nowrap">{formatDate(order.created_at)}</td>
						<td class="px-4 py-3 whitespace-nowrap">
							<button
								class="flex items-center gap-1.5 group"
								on:click={() => copyOrderNo(order.out_trade_no)}
								title={$i18n.t('点击复制')}
							>
								<code
									class="px-2.5 py-1 bg-gray-100/80 dark:bg-gray-700/80 rounded-lg text-xs font-mono group-hover:bg-indigo-50 dark:group-hover:bg-indigo-900/30 group-hover:text-indigo-700 dark:group-hover:text-indigo-300 transition-all backdrop-blur-sm"
								>
									{order.out_trade_no}
								</code>
								<svg
									class="w-3.5 h-3.5 text-gray-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
									/>
								</svg>
							</button>
						</td>
						<td class="px-4 py-3 text-right whitespace-nowrap">
							<div class="flex flex-col items-end gap-1">
								<span class="text-sm font-bold text-green-600 dark:text-green-400">
									+¥{order.amount.toFixed(2)}
								</span>
								{#if order.is_first_recharge && order.bonus_amount && order.bonus_amount > 0}
									<div class="flex items-center gap-1 px-2 py-0.5 rounded-md bg-gradient-to-r from-amber-100 to-orange-100 dark:from-amber-900/30 dark:to-orange-900/30 border border-amber-300/50 dark:border-amber-600/50">
										<svg class="w-3 h-3 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
										</svg>
										<span class="text-xs font-semibold text-amber-700 dark:text-amber-400">
											{$i18n.t('首充奖励')} +¥{order.bonus_amount.toFixed(2)}
										</span>
									</div>
								{/if}
							</div>
						</td>
						<td class="px-4 py-3 text-center whitespace-nowrap">
							<span
								class="inline-block px-2.5 py-1 rounded-lg text-xs font-semibold backdrop-blur-sm {getStatusClass(
									order.status
								)}"
							>
								{getStatusLabel(order.status)}
							</span>
						</td>
						<td class="px-4 py-3 text-sm whitespace-nowrap text-gray-600 dark:text-gray-400">
							{order.paid_at ? formatDate(order.paid_at) : '-'}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>

		{#if loading}
			<div class="flex justify-center items-center py-8">
				<Spinner />
			</div>
		{/if}

		{#if !loading && hasMore && orders.length > 0}
			<div class="flex justify-center py-4 px-4">
				<button
					class="px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white rounded-xl font-semibold transition-all duration-200 shadow-md hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]"
					on:click={loadOrders}
				>
					{$i18n.t('加载更多')}
				</button>
			</div>
		{/if}

		{#if !loading && orders.length === 0}
			<div class="flex flex-col items-center justify-center py-16 text-gray-400 dark:text-gray-500">
				<div class="p-4 bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-2xl mb-4">
					<svg
						class="w-16 h-16 text-indigo-400 dark:text-indigo-500"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="1.5"
							d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
						/>
					</svg>
				</div>
				<p class="text-sm font-medium">{$i18n.t('暂无充值记录')}</p>
			</div>
		{/if}
	</div>
</div>

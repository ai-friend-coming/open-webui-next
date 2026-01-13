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

<div class="payment-orders-table bg-white dark:bg-gray-850 rounded-xl shadow-sm">
	<div class="table-header px-4 py-3 border-b border-gray-100 dark:border-gray-800">
		<h2 class="text-lg font-semibold">{$i18n.t('充值记录')}</h2>
	</div>

	<div class="table-container overflow-x-auto">
		<table class="w-full">
			<thead>
				<tr class="bg-gray-50 dark:bg-gray-800">
					<th class="px-4 py-3 text-left text-xs font-semibold whitespace-nowrap"
						>{$i18n.t('时间')}</th
					>
					<th class="px-4 py-3 text-left text-xs font-semibold whitespace-nowrap"
						>{$i18n.t('订单号')}</th
					>
					<th class="px-4 py-3 text-right text-xs font-semibold whitespace-nowrap"
						>{$i18n.t('金额')}</th
					>
					<th class="px-4 py-3 text-center text-xs font-semibold whitespace-nowrap"
						>{$i18n.t('状态')}</th
					>
					<th class="px-4 py-3 text-left text-xs font-semibold whitespace-nowrap"
						>{$i18n.t('支付时间')}</th
					>
				</tr>
			</thead>
			<tbody>
				{#each orders as order (order.id)}
					<tr
						class="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
					>
						<td class="px-4 py-3 text-sm whitespace-nowrap">{formatDate(order.created_at)}</td>
						<td class="px-4 py-3 whitespace-nowrap">
							<button
								class="flex items-center gap-1.5 group"
								on:click={() => copyOrderNo(order.out_trade_no)}
								title={$i18n.t('点击复制')}
							>
								<code
									class="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-xs font-mono group-hover:bg-gray-200 dark:group-hover:bg-gray-700 transition"
								>
									{order.out_trade_no}
								</code>
								<svg
									class="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition"
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
						<td class="px-4 py-3 text-right text-sm font-semibold whitespace-nowrap text-green-600">
							+¥{order.amount.toFixed(2)}
						</td>
						<td class="px-4 py-3 text-center whitespace-nowrap">
							<span
								class="inline-block px-2 py-0.5 rounded text-xs font-medium {getStatusClass(
									order.status
								)}"
							>
								{getStatusLabel(order.status)}
							</span>
						</td>
						<td class="px-4 py-3 text-sm whitespace-nowrap text-gray-500 dark:text-gray-400">
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
			<div class="flex justify-center py-4">
				<button
					class="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg font-medium transition"
					on:click={loadOrders}
				>
					{$i18n.t('加载更多')}
				</button>
			</div>
		{/if}

		{#if !loading && orders.length === 0}
			<div class="flex flex-col items-center justify-center py-12 text-gray-500">
				<svg
					class="w-16 h-16 mb-4 opacity-50"
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
				<p class="text-sm">{$i18n.t('暂无充值记录')}</p>
			</div>
		{/if}
	</div>
</div>

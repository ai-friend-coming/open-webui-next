<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { getPaymentStatus, getBalance } from '$lib/apis/billing';
	import { balance } from '$lib/stores';

	const i18n = getContext('i18n');

	let status: 'loading' | 'paid' | 'pending' | 'error' = 'loading';
	let orderAmount: number | null = null;
	let errorMessage = '';

	onMount(async () => {
		// 从 URL 参数获取订单信息
		const orderId = $page.url.searchParams.get('order_id');
		const orderStatus = $page.url.searchParams.get('status');
		const error = $page.url.searchParams.get('error');

		if (error) {
			status = 'error';
			errorMessage = error === 'order_not_found' ? $i18n.t('订单不存在') : $i18n.t('支付失败');
			return;
		}

		// 如果 URL 没有订单信息，尝试从 sessionStorage 恢复
		let targetOrderId = orderId;
		if (!targetOrderId) {
			const pendingOrder = sessionStorage.getItem('pending_payment_order');
			if (pendingOrder) {
				try {
					const parsed = JSON.parse(pendingOrder);
					targetOrderId = parsed.order_id;
				} catch (e) {
					console.error('解析待支付订单失败', e);
				}
			}
		}

		if (!targetOrderId) {
			status = 'error';
			errorMessage = $i18n.t('未找到订单信息');
			return;
		}

		// 检查登录状态
		const token = localStorage.getItem('token');
		if (!token) {
			console.error('未登录，无法查询订单状态');
			status = 'error';
			errorMessage = $i18n.t('请先登录');
			return;
		}

		console.log('查询订单状态:', targetOrderId);

		// 查询订单状态
		try {
			const result = await getPaymentStatus(token, targetOrderId);
			console.log('订单状态结果:', result);
			orderAmount = result.amount;

			if (result.status === 'paid') {
				status = 'paid';

				// 清理 sessionStorage
				sessionStorage.removeItem('pending_payment_order');

				// 刷新用户余额
				try {
					const balanceInfo = await getBalance(localStorage.token);
					balance.set(balanceInfo);
				} catch (e) {
					console.error('刷新余额失败', e);
				}
			} else if (result.status === 'pending') {
				status = 'pending';
			} else {
				status = 'error';
				errorMessage = $i18n.t('订单状态异常');
			}
		} catch (e: any) {
			console.error('查询订单状态失败', e);
			status = 'error';
			errorMessage = e.detail || $i18n.t('查询订单失败');
		}
	});

	const goHome = () => {
		goto('/');
	};

	const goBilling = () => {
		goto('/billing');
	};

	const retry = () => {
		window.location.reload();
	};
</script>

<div class="min-h-screen flex items-center justify-center p-4">
	<div
		class="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8 text-center space-y-6"
	>
		{#if status === 'loading'}
			<!-- 加载中 -->
			<div class="space-y-4">
				<div
					class="w-16 h-16 mx-auto border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"
				></div>
				<p class="text-gray-600 dark:text-gray-400">{$i18n.t('正在查询支付结果...')}</p>
			</div>
		{:else if status === 'paid'}
			<!-- 支付成功 -->
			<div class="space-y-4">
				<div
					class="w-20 h-20 mx-auto bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center"
				>
					<svg
						class="w-10 h-10 text-green-500"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M5 13l4 4L19 7"
						/>
					</svg>
				</div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-white">{$i18n.t('支付成功')}</h1>
				{#if orderAmount}
					<p class="text-3xl font-bold text-green-500">¥{orderAmount}</p>
				{/if}
				<p class="text-gray-500 dark:text-gray-400">{$i18n.t('充值金额已到账')}</p>
				<div class="flex gap-3 justify-center pt-4">
					<button
						on:click={goBilling}
						class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
					>
						{$i18n.t('查看余额')}
					</button>
					<button
						on:click={goHome}
						class="px-6 py-2.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg transition-colors"
					>
						{$i18n.t('返回首页')}
					</button>
				</div>
			</div>
		{:else if status === 'pending'}
			<!-- 等待确认 -->
			<div class="space-y-4">
				<div
					class="w-20 h-20 mx-auto bg-yellow-100 dark:bg-yellow-900/30 rounded-full flex items-center justify-center"
				>
					<svg
						class="w-10 h-10 text-yellow-500"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-white">
					{$i18n.t('等待支付确认')}
				</h1>
				<p class="text-gray-500 dark:text-gray-400">
					{$i18n.t('如已完成支付，请稍等片刻')}
				</p>
				<div class="flex gap-3 justify-center pt-4">
					<button
						on:click={retry}
						class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
					>
						{$i18n.t('刷新状态')}
					</button>
					<button
						on:click={goHome}
						class="px-6 py-2.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg transition-colors"
					>
						{$i18n.t('返回首页')}
					</button>
				</div>
			</div>
		{:else}
			<!-- 错误 -->
			<div class="space-y-4">
				<div
					class="w-20 h-20 mx-auto bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center"
				>
					<svg
						class="w-10 h-10 text-red-500"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-white">{$i18n.t('支付失败')}</h1>
				<p class="text-gray-500 dark:text-gray-400">{errorMessage || $i18n.t('请重新尝试')}</p>
				<div class="flex gap-3 justify-center pt-4">
					<button
						on:click={goBilling}
						class="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
					>
						{$i18n.t('重新充值')}
					</button>
					<button
						on:click={goHome}
						class="px-6 py-2.5 bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium rounded-lg transition-colors"
					>
						{$i18n.t('返回首页')}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

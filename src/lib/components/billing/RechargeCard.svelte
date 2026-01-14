<script lang="ts">
	import { onMount, onDestroy, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import {
		createPaymentOrder,
		createH5PaymentOrder,
		getPaymentConfig,
		getPaymentStatus
	} from '$lib/apis/billing';
	import { getBalance } from '$lib/apis/billing';
	import { balance } from '$lib/stores';
	import PaymentSuccessModal from './PaymentSuccessModal.svelte';

	const i18n = getContext('i18n');

	// 支付场景专用：仅基于 User-Agent 判断是否为移动设备
	// 不考虑窗口宽度，避免桌面端窄窗口误判
	const isMobilePayment = (): boolean => {
		if (typeof window === 'undefined') return false;
		return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
			navigator.userAgent
		);
	};

	// 预设金额选项
	const amountOptions = [10, 50, 100, 200, 500, 1000];

	let selectedAmount: number | null = null;
	let customAmount = '';
	let loading = false;
	let alipayEnabled = false;
	let checkingPayment = false; // 正在检查支付状态

	// 成功弹窗状态
	let showSuccessModal = false;
	let successAmount = 0;

	// 计算最终金额
	$: finalAmount = selectedAmount || (customAmount ? parseFloat(customAmount) : 0);
	$: isValidAmount = finalAmount >= 0.01 && finalAmount <= 10000;

	// 检查待支付订单状态（用于移动端从支付宝 App 返回后）
	const checkPendingOrder = async () => {
		const pendingOrderStr = sessionStorage.getItem('pending_payment_order');
		if (!pendingOrderStr) return;

		try {
			const pendingOrder = JSON.parse(pendingOrderStr);
			const now = Math.floor(Date.now() / 1000);

			// 检查订单是否过期
			if (pendingOrder.expired_at && pendingOrder.expired_at < now) {
				sessionStorage.removeItem('pending_payment_order');
				loading = false;
				return;
			}

			checkingPayment = true;
			const result = await getPaymentStatus(localStorage.token, pendingOrder.order_id);

			if (result.status === 'paid') {
				// 支付成功
				sessionStorage.removeItem('pending_payment_order');

				// 显示成功弹窗
				successAmount = result.amount;
				showSuccessModal = true;

				// 刷新余额
				try {
					const balanceInfo = await getBalance(localStorage.token);
					balance.set(balanceInfo);
				} catch (e) {
					console.error('刷新余额失败', e);
				}

				loading = false;
			} else if (result.status === 'pending') {
				// 仍在等待支付，保持 loading 但允许用户取消
				loading = true;
			} else {
				// 订单已关闭或其他状态
				sessionStorage.removeItem('pending_payment_order');
				loading = false;
			}
		} catch (e) {
			console.error('检查订单状态失败', e);
			loading = false;
		} finally {
			checkingPayment = false;
		}
	};

	// 取消等待支付
	const cancelWaiting = () => {
		sessionStorage.removeItem('pending_payment_order');
		loading = false;
		toast.info($i18n.t('已取消等待'));
	};

	// 页面可见性变化处理（用于移动端从支付宝 App 返回）
	const handleVisibilityChange = () => {
		if (document.visibilityState === 'visible') {
			// 页面重新可见，检查是否有待支付订单
			checkPendingOrder();
		}
	};

	// 检查支付配置
	onMount(async () => {
		try {
			const config = await getPaymentConfig();
			alipayEnabled = config.alipay_enabled;
		} catch (e) {
			console.error('获取支付配置失败', e);
		}

		// 检查是否有待支付订单（页面刷新或返回时）
		checkPendingOrder();

		// 监听页面可见性变化
		document.addEventListener('visibilitychange', handleVisibilityChange);
	});

	onDestroy(() => {
		document.removeEventListener('visibilitychange', handleVisibilityChange);
	});

	// 创建订单并跳转支付
	const createOrder = async () => {
		if (!isValidAmount) return;

		loading = true;
		try {
			// 根据设备类型选择不同的支付接口
			const isMobile = isMobilePayment();
			const result = isMobile
				? await createH5PaymentOrder(localStorage.token, finalAmount)
				: await createPaymentOrder(localStorage.token, finalAmount);

			// 保存订单信息到 sessionStorage，支付完成后返回时使用
			sessionStorage.setItem(
				'pending_payment_order',
				JSON.stringify({
					order_id: result.order_id,
					amount: result.amount,
					expired_at: result.expired_at
				})
			);

			// 跳转到支付宝收银台
			window.location.href = result.pay_url;
		} catch (error: any) {
			toast.error(error.detail || error || $i18n.t('创建订单失败'));
			loading = false;
		}
	};
</script>

<div
	class="p-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm"
>
	<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
		{$i18n.t('账户充值')}
	</h3>

	{#if !alipayEnabled}
		<!-- 支付未配置 -->
		<div class="text-center py-6 text-gray-500 dark:text-gray-400">
			<svg
				class="w-12 h-12 mx-auto mb-3 opacity-50"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="1.5"
					d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
				/>
			</svg>
			<p class="text-sm">{$i18n.t('充值功能暂未开放')}</p>
			<p class="text-xs mt-1">{$i18n.t('请联系管理员')}</p>
		</div>
	{:else}
		<!-- 金额选择 -->
		<div class="space-y-4">
			<div class="grid grid-cols-3 gap-2">
				{#each amountOptions as amount}
					<button
						class="py-2 px-3 rounded-lg border text-sm font-medium transition-colors
							{selectedAmount === amount
							? 'border-indigo-500 bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400'
							: 'border-gray-200 dark:border-gray-600 hover:border-indigo-300 dark:hover:border-indigo-500 text-gray-700 dark:text-gray-300'}"
						on:click={() => {
							selectedAmount = amount;
							customAmount = '';
						}}
					>
						¥{amount}
					</button>
				{/each}
			</div>

			<!-- 自定义金额 -->
			<div>
				<input
					type="number"
					bind:value={customAmount}
					on:input={() => (selectedAmount = null)}
					placeholder={$i18n.t('自定义金额 (0.01-10000)')}
					class="w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg
						bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100
						focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
				/>
			</div>

			<!-- 充值按钮 -->
			<button
				on:click={createOrder}
				disabled={!isValidAmount || loading}
				class="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 dark:disabled:bg-gray-600
					text-white font-medium rounded-lg transition-colors disabled:cursor-not-allowed"
			>
				{#if loading}
					<span class="flex items-center justify-center gap-2">
						<span
							class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"
						></span>
						{#if checkingPayment}
							{$i18n.t('正在检查支付状态...')}
						{:else}
							{$i18n.t('正在跳转支付...')}
						{/if}
					</span>
				{:else}
					{$i18n.t('立即充值')} {isValidAmount ? `¥${finalAmount}` : ''}
				{/if}
			</button>

			<!-- 取消等待按钮（移动端从支付宝返回后可能需要） -->
			{#if loading}
				<button
					on:click={cancelWaiting}
					class="w-full py-2 text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
				>
					{$i18n.t('取消等待 / 重新选择金额')}
				</button>
			{/if}

			<p class="text-xs text-gray-500 dark:text-gray-400 text-center">
				{$i18n.t('支持支付宝支付')}
			</p>
		</div>
	{/if}
</div>

<!-- 充值成功弹窗 -->
<PaymentSuccessModal bind:show={showSuccessModal} amount={successAmount} />

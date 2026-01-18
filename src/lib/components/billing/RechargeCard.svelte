<script lang="ts">
	import { onMount, onDestroy, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import {
		createPaymentOrder,
		createH5PaymentOrder,
		getPaymentConfig,
		getPaymentStatus,
		getFirstRechargeBonusConfig,
		checkFirstRechargeBonusEligibility,
		type FirstRechargeBonusConfig,
		type FirstRechargeBonusEligibility
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

	// 计算每个档位的首充奖励金额
	const calculateBonus = (amount: number): number => {
		if (!firstRechargeBonusConfig || !showFirstRechargeBanner) return 0;
		const bonus = (amount * firstRechargeBonusConfig.rate) / 100;
		return Math.min(bonus, firstRechargeBonusConfig.max_amount);
	};

	// 成功弹窗状态
	let showSuccessModal = false;
	let successAmount = 0;
	let successBonusAmount = 0;
	let successBonusRate = 0;

	// 首充优惠相关状态
	let firstRechargeBonusConfig: FirstRechargeBonusConfig | null = null;
	let firstRechargeBonusEligibility: FirstRechargeBonusEligibility | null = null;
	let showFirstRechargeBanner = false;

	// 计算最终金额
	$: finalAmount = selectedAmount || (customAmount ? parseFloat(customAmount) : 0);
	$: isValidAmount = finalAmount >= 0.01 && finalAmount <= 10000;

	// 计算预期首充奖励
	$: expectedBonus =
		firstRechargeBonusConfig && showFirstRechargeBanner && finalAmount > 0
			? Math.min((finalAmount * firstRechargeBonusConfig.rate) / 100, firstRechargeBonusConfig.max_amount)
			: 0;

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
				successBonusAmount = result.bonus_amount || 0;
				successBonusRate = result.bonus_rate || 0;
				showSuccessModal = true;

				// 如果是首充，隐藏首充横幅
				if (result.is_first_recharge) {
					showFirstRechargeBanner = false;
				}

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

		// 加载首充优惠配置和资格检查
		try {
			// 获取首充优惠配置（公开接口）
			const bonusConfig = await getFirstRechargeBonusConfig();
			firstRechargeBonusConfig = bonusConfig;

			// 检查用户资格（需要登录）
			if (localStorage.token) {
				const eligibility = await checkFirstRechargeBonusEligibility(localStorage.token);
				firstRechargeBonusEligibility = eligibility;

				// 同时满足以下条件才显示横幅
				showFirstRechargeBanner =
					bonusConfig.enabled && eligibility.eligible;
			}
		} catch (e) {
			console.error('获取首充优惠信息失败', e);
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
	class="p-5 bg-white/70 dark:bg-gray-800/70 backdrop-blur-xl rounded-2xl border border-white/30 dark:border-gray-700/50 shadow-lg hover:shadow-xl transition-all duration-300"
>
	<div class="flex items-center gap-2.5 mb-4">
		<div class="p-2 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg">
			<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
			</svg>
		</div>
		<h3 class="text-lg font-semibold text-gray-900 dark:text-white">
			{$i18n.t('账户充值')}
		</h3>
	</div>

	<!-- 首充优惠横幅 -->
	{#if showFirstRechargeBanner && firstRechargeBonusConfig}
		<div
			class="mb-4 p-4 rounded-xl border-2 backdrop-blur-xl
				bg-gradient-to-br from-amber-50/90 to-orange-50/90 dark:from-amber-900/20 dark:to-orange-900/20
				border-amber-300/60 dark:border-amber-600/60
				shadow-lg shadow-amber-500/10 dark:shadow-amber-500/5
				transition-all duration-300 hover:shadow-xl hover:shadow-amber-500/20"
		>
			<div class="flex items-start gap-3">
				<!-- 礼物图标 -->
				<div class="flex-shrink-0 mt-0.5">
					<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center shadow-md">
						<svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
						</svg>
					</div>
				</div>

				<!-- 活动内容 -->
				<div class="flex-1 min-w-0">
					<div class="flex items-center gap-2 mb-1">
						<h4 class="text-base font-bold bg-gradient-to-r from-amber-600 to-orange-600 dark:from-amber-400 dark:to-orange-400 bg-clip-text text-transparent">
							{$i18n.t('🎉 首充优惠')}
						</h4>
					</div>
					<p class="text-sm text-gray-700 dark:text-gray-300 mb-2">
						{$i18n.t('新用户首次充值享受')}
						<span class="font-bold text-amber-600 dark:text-amber-400">{firstRechargeBonusConfig.rate}%</span>
						{$i18n.t('返现')}，
						{$i18n.t('最高')}
						<span class="font-bold text-amber-600 dark:text-amber-400">¥{firstRechargeBonusConfig.max_amount.toFixed(2)}</span>
					</p>

					<!-- 预期奖励提示 -->
					{#if expectedBonus > 0}
						<div class="flex items-center gap-1.5 text-xs">
							<svg class="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
							</svg>
							<span class="text-gray-600 dark:text-gray-400">
								{$i18n.t('充值')} ¥{finalAmount.toFixed(2)}，{$i18n.t('您将获得')}
								<span class="font-bold text-amber-600 dark:text-amber-400">¥{expectedBonus.toFixed(2)}</span>
								{$i18n.t('奖励')}
							</span>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}

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
			<div class="grid grid-cols-3 gap-2.5">
				{#each amountOptions as amount}
					<button
						class="relative py-2.5 px-3 rounded-xl border text-sm font-semibold transition-all duration-200
							{selectedAmount === amount
							? 'border-indigo-500 bg-gradient-to-br from-indigo-50 to-purple-50 text-indigo-700 dark:from-indigo-900/40 dark:to-purple-900/40 dark:text-indigo-300 shadow-md scale-105'
							: 'border-gray-200/60 dark:border-gray-600/60 hover:border-indigo-300 dark:hover:border-indigo-500 text-gray-700 dark:text-gray-300 hover:shadow-md hover:scale-102 bg-white/50 dark:bg-gray-700/50'}"
						on:click={() => {
							selectedAmount = amount;
							customAmount = '';
						}}
					>
						<!-- 首充奖励浮动标签 -->
						{#if showFirstRechargeBanner && calculateBonus(amount) > 0}
							<div class="absolute -top-2 -right-2 px-1.5 sm:px-2 py-0.5 rounded-full text-[10px] sm:text-xs font-bold
								bg-gradient-to-r from-amber-400 to-orange-500 text-white shadow-lg
								flex items-center gap-0.5 animate-bounce-subtle whitespace-nowrap z-10">
								<span class="text-[9px] sm:text-[10px]">🎁</span>
								<span>+¥{calculateBonus(amount).toFixed(0)}</span>
							</div>
						{/if}
						<span class="relative z-0">¥{amount}</span>
					</button>
				{/each}
			</div>

			<!-- 自定义金额 -->
			<div class="relative">
				<input
					type="number"
					bind:value={customAmount}
					on:input={() => (selectedAmount = null)}
					placeholder={$i18n.t('自定义金额 (0.01-10000)')}
					class="w-full px-4 py-2.5 border rounded-xl text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400
						focus:ring-2 focus:ring-indigo-500 focus:border-transparent backdrop-blur-sm transition-all
						{showFirstRechargeBanner
							? 'border-amber-300/60 dark:border-amber-600/60 bg-gradient-to-r from-amber-50/50 to-white/50 dark:from-amber-900/10 dark:to-gray-700/50'
							: 'border-gray-200/60 dark:border-gray-600/60 bg-white/50 dark:bg-gray-700/50'}"
				/>
				{#if showFirstRechargeBanner}
					<div class="mt-1.5 text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
						<span>✨</span>
						<span>{$i18n.t('自定义金额同样享受首充')} {firstRechargeBonusConfig?.rate}% {$i18n.t('奖励')}</span>
					</div>
				{/if}
			</div>

			<!-- 实时计算展示卡片 -->
			{#if showFirstRechargeBanner && finalAmount > 0 && expectedBonus > 0}
				<div class="p-4 rounded-xl bg-gradient-to-br from-amber-50/80 to-orange-50/80 dark:from-amber-900/20 dark:to-orange-900/20
					border border-amber-200/50 dark:border-amber-600/30 backdrop-blur-sm space-y-2.5">
					<!-- 充值金额 -->
					<div class="flex items-center justify-between text-sm">
						<span class="text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
							<svg class="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
							</svg>
							{$i18n.t('充值金额')}
						</span>
						<span class="font-semibold text-gray-900 dark:text-gray-100">¥{finalAmount.toFixed(2)}</span>
					</div>

					<!-- 首充奖励 -->
					<div class="flex items-center justify-between text-sm">
						<span class="text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
							<span class="text-base">🎁</span>
							{$i18n.t('首充奖励')} ({firstRechargeBonusConfig.rate}%)
						</span>
						<span class="font-bold text-amber-600 dark:text-amber-400">+¥{expectedBonus.toFixed(2)}</span>
					</div>

					<!-- 分隔线 -->
					<div class="border-t border-amber-200/50 dark:border-amber-600/30"></div>

					<!-- 实际到账 -->
					<div class="flex items-center justify-between">
						<span class="text-gray-700 dark:text-gray-300 flex items-center gap-1.5 font-medium">
							<svg class="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
								<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
							</svg>
							{$i18n.t('实际到账')}
						</span>
						<span class="text-lg font-bold bg-gradient-to-r from-green-600 to-emerald-600 dark:from-green-400 dark:to-emerald-400 bg-clip-text text-transparent">
							¥{(finalAmount + expectedBonus).toFixed(2)}
						</span>
					</div>
				</div>
			{/if}

			<!-- 充值按钮 -->
			<button
				on:click={createOrder}
				disabled={!isValidAmount || loading}
				class="w-full py-3 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700
					disabled:from-gray-300 disabled:to-gray-300 dark:disabled:from-gray-600 dark:disabled:to-gray-600
					text-white font-semibold rounded-xl transition-all duration-200 disabled:cursor-not-allowed
					shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] disabled:hover:scale-100"
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
					class="w-full py-2 text-sm text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 transition-colors font-medium"
				>
					{$i18n.t('取消等待 / 重新选择金额')}
				</button>
			{/if}

			<div class="flex items-center justify-center gap-2 text-xs text-gray-500 dark:text-gray-400">
				<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
					<path d="M3.75 21h16.5M4.5 3h15l-3.86 14.14a2 2 0 01-1.93 1.5H8.29a2 2 0 01-1.93-1.5L2.5 3h2z"/>
				</svg>
				<span>{$i18n.t('支持支付宝支付')}</span>
			</div>
		</div>
	{/if}
</div>

<!-- 充值成功弹窗 -->
<PaymentSuccessModal
	bind:show={showSuccessModal}
	amount={successAmount}
	bonusAmount={successBonusAmount}
	bonusRate={successBonusRate}
/>

<style>
	@keyframes bounce-subtle {
		0%, 100% {
			transform: translateY(0) scale(1);
		}
		50% {
			transform: translateY(-2px) scale(1.02);
		}
	}

	.animate-bounce-subtle {
		animation: bounce-subtle 2s ease-in-out infinite;
	}
</style>

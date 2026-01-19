<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		signIn,
		getSignInStatus,
		getPublicConfig,
		type SignInStatus
	} from '$lib/apis/sign-in';
	import Spinner from '$lib/components/common/Spinner.svelte';

	// 签到状态
	let status: SignInStatus | null = null;
	let statusLoading = true;
	let isEnabled = false;

	// 签到动画状态
	let isSigningIn = false;
	let reward: number | null = null;
	let showReward = false;

	// 扭蛋机动画状态
	let machineShaking = false;
	let capsuleFalling = false;
	let capsuleOpening = false;
	let coinsFlying = false;

	// 加载公开配置
	const loadPublicConfig = async () => {
		try {
			const config = await getPublicConfig();
			isEnabled = config.enabled;
		} catch (error) {
			console.error('加载签到配置失败:', error);
			isEnabled = false;
		}
	};

	// 加载签到状态
	const loadStatus = async () => {
		statusLoading = true;
		try {
			status = await getSignInStatus(localStorage.token);
		} catch (error) {
			console.error('加载签到状态失败:', error);
		} finally {
			statusLoading = false;
		}
	};

	// 执行签到
	const handleSignIn = async () => {
		if (!status || status.has_signed_today) return;

		isSigningIn = true;
		reward = null;
		showReward = false;

		try {
			// 步骤1: 扭蛋机摇晃 (800ms)
			machineShaking = true;
			await new Promise((resolve) => setTimeout(resolve, 800));
			machineShaking = false;

			// 步骤2: 扭蛋掉落 (600ms)
			capsuleFalling = true;
			await new Promise((resolve) => setTimeout(resolve, 600));

			// 执行签到 API 调用（在动画进行时）
			const response = await signIn(localStorage.token);

			// 步骤3: 扭蛋打开 (400ms)
			capsuleOpening = true;
			await new Promise((resolve) => setTimeout(resolve, 400));

			// 步骤4: 金币飞出 (600ms)
			coinsFlying = true;
			await new Promise((resolve) => setTimeout(resolve, 600));

			// 设置最终奖励
			reward = response.amount;

			// 重置动画状态
			capsuleFalling = false;
			capsuleOpening = false;
			coinsFlying = false;

			// 显示奖励弹窗
			showReward = true;

			// 重新加载状态
			await loadStatus();

			// 显示成功消息
			toast.success(response.message);
		} catch (error: any) {
			// 重置所有动画状态
			machineShaking = false;
			capsuleFalling = false;
			capsuleOpening = false;
			coinsFlying = false;
			toast.error(error || '签到失败，请稍后重试');
		} finally {
			isSigningIn = false;
		}
	};

	// 关闭奖励显示
	const closeReward = () => {
		showReward = false;
		reward = null;
	};

	onMount(async () => {
		await loadPublicConfig();
		if (isEnabled) {
			await loadStatus();
		}
	});
</script>

{#if isEnabled}
	<div class="relative bg-gradient-to-br from-pink-50 to-purple-50 dark:from-pink-900/20 dark:to-purple-900/20 border-2 border-pink-200 dark:border-pink-800 rounded-2xl p-6 shadow-lg">
		<!-- 背景装饰 -->
		<div class="absolute top-0 left-0 w-full h-full overflow-hidden rounded-2xl pointer-events-none">
			<div class="absolute top-2 right-2 text-4xl opacity-20">✨</div>
			<div class="absolute bottom-2 left-2 text-4xl opacity-20">🌟</div>
			<div class="absolute top-1/2 left-1/4 text-3xl opacity-10">⭐</div>
		</div>

		<!-- 内容 -->
		<div class="relative z-10">
			<!-- 标题 -->
			<div class="text-center mb-6">
				<h3 class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-pink-600 to-purple-600 dark:from-pink-400 dark:to-purple-400 mb-2">
					✨ 每日签到 ✨
				</h3>
				<p class="text-sm text-gray-600 dark:text-gray-300 mb-3">
					每天签到领取随机奖励哦~
				</p>

				<!-- 签到进度条 -->
				{#if status}
					<div class="flex items-center justify-center gap-2 mt-3">
						{#each Array(5) as _, i}
							{@const dayNum = i + 1}
							{@const isSigned = dayNum <= (status.continuous_days % 5 || (status.continuous_days > 0 && status.continuous_days % 5 === 0 ? 5 : 0))}
							{@const isToday = dayNum === (status.continuous_days % 5 || (status.continuous_days > 0 && status.continuous_days % 5 === 0 ? 5 : 0)) && status.has_signed_today}

							<div class="flex flex-col items-center gap-1">
								<div class="relative">
									{#if isToday}
										<!-- 今天刚签到 -->
										<div class="w-9 h-9 rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 border-2 border-yellow-300 flex items-center justify-center text-lg animate-pulse shadow-lg">
											🎁
										</div>
									{:else if isSigned}
										<!-- 已签到 -->
										<div class="w-9 h-9 rounded-full bg-gradient-to-br from-pink-500 to-purple-500 border-2 border-pink-400 flex items-center justify-center shadow-md">
											<svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
												<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
											</svg>
										</div>
									{:else}
										<!-- 未签到 -->
										<div class="w-9 h-9 rounded-full bg-gray-200 dark:bg-gray-700 border-2 border-gray-300 dark:border-gray-600 flex items-center justify-center">
											<span class="text-xs text-gray-400 dark:text-gray-500">{dayNum}</span>
										</div>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			{#if statusLoading}
				<div class="flex items-center justify-center py-8">
					<Spinner className="size-8" />
				</div>
			{:else if status}
				<!-- 签到状态卡片 -->
				<div class="bg-white dark:bg-gray-800/80 backdrop-blur-sm rounded-xl p-5 mb-4 border border-pink-100 dark:border-pink-900/50">
					<div class="grid grid-cols-2 gap-4 text-center">
						<!-- 连续签到天数 -->
						<div>
							<div class="text-3xl font-bold text-pink-600 dark:text-pink-400">
								{status.continuous_days}
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								连续签到
							</div>
						</div>

						<!-- 本月签到天数 -->
						<div>
							<div class="text-3xl font-bold text-purple-600 dark:text-purple-400">
								{status.month_days}
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								本月签到
							</div>
						</div>

						<!-- 累计签到天数 -->
						<div>
							<div class="text-2xl font-bold text-blue-600 dark:text-blue-400">
								{status.total_days}
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								累计天数
							</div>
						</div>

						<!-- 累计奖励 -->
						<div>
							<div class="text-2xl font-bold text-red-600 dark:text-red-400 flex items-center justify-center gap-1">
								<span class="text-xl">🧧</span>
								<span>¥{status.total_amount.toFixed(2)}</span>
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								累计奖励
							</div>
						</div>
					</div>
				</div>

				<!-- 扭蛋机和签到按钮 -->
				<div class="text-center">
					{#if status.has_signed_today}
						<!-- 已签到 -->
						<div class="mb-4">
							<div class="py-6 px-8 bg-gray-100 dark:bg-gray-800/50 rounded-xl border-2 border-gray-200 dark:border-gray-700">
								<p class="text-base font-medium text-gray-500 dark:text-gray-400 mb-4">
									✓ 今日已领取
								</p>
								<a
									href="/billing"
									class="inline-flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-medium rounded-lg transition-all duration-200 hover:scale-105 shadow-md"
								>
									<span>💰</span>
									<span>去使用余额</span>
								</a>
								<p class="text-xs text-gray-400 dark:text-gray-500 mt-3">
									明天再来签到吧~
								</p>
							</div>
						</div>
					{:else}
						<!-- 扭蛋机容器 -->
						<div class="mb-6 flex items-center justify-center min-h-[280px] relative">
							<!-- 扭蛋机 -->
							<div class="gashapon-machine {machineShaking ? 'shaking' : ''}">
								<!-- 扭蛋机顶部玻璃球 -->
								<div class="machine-globe">
									<div class="glass-shine"></div>
									<!-- 扭蛋们 -->
									<div class="capsules-container">
										<div class="capsule-mini" style="top: 20%; left: 30%; background: linear-gradient(135deg, #ff6b9d 0%, #c94b7f 100%);"></div>
										<div class="capsule-mini" style="top: 40%; left: 60%; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);"></div>
										<div class="capsule-mini" style="top: 60%; left: 25%; background: linear-gradient(135deg, #ffd93d 0%, #ffb800 100%);"></div>
										<div class="capsule-mini" style="top: 35%; left: 70%; background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);"></div>
										<div class="capsule-mini" style="top: 70%; left: 55%; background: linear-gradient(135deg, #c471f5 0%, #fa71cd 100%);"></div>
									</div>
								</div>

								<!-- 扭蛋机底座 -->
								<div class="machine-base">
									<div class="machine-opening"></div>
								</div>

								<!-- 扭蛋机旋钮 -->
								<div class="machine-knob"></div>
							</div>

							<!-- 掉落的扭蛋 -->
							{#if capsuleFalling || capsuleOpening || coinsFlying}
								<div class="falling-capsule {capsuleFalling ? 'falling' : ''} {capsuleOpening ? 'opening' : ''}">
									<div class="capsule-half capsule-top"></div>
									<div class="capsule-half capsule-bottom"></div>

									<!-- 金币飞出效果 -->
									{#if coinsFlying}
										<div class="coin coin-1">💰</div>
										<div class="coin coin-2">💰</div>
										<div class="coin coin-3">💰</div>
										<div class="coin coin-4">🪙</div>
										<div class="coin coin-5">🪙</div>
									{/if}
								</div>
							{/if}
						</div>

						<!-- 签到按钮 -->
						<button
							class="px-8 py-3 bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white font-bold rounded-full text-lg shadow-lg transform hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
							on:click={handleSignIn}
							disabled={isSigningIn}
						>
							{#if isSigningIn}
								<span class="flex items-center gap-2">
									<Spinner className="size-5" />
									扭蛋中...
								</span>
							{:else}
								🎁 转动扭蛋
							{/if}
						</button>
					{/if}
				</div>
			{/if}
		</div>
	</div>

	<!-- 奖励弹窗 -->
	{#if showReward && reward !== null}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" on:click={closeReward}>
			<div class="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-2xl max-w-sm mx-4 transform animate-bounce" on:click|stopPropagation>
				<!-- 关闭按钮 -->
				<button
					class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
					on:click={closeReward}
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>

				<!-- 奖励内容 -->
				<div class="text-center">
					<div class="text-6xl mb-4">🎉</div>
					<h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">
						签到成功！
					</h3>
					<p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
						恭喜你获得了
					</p>
					<div class="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-yellow-500 to-orange-500 mb-6">
						¥{reward.toFixed(2)}
					</div>
					<button
						class="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600 text-white font-medium rounded-full"
						on:click={closeReward}
					>
						太棒了！
					</button>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	/* 扭蛋机主体 */
	.gashapon-machine {
		position: relative;
		width: 180px;
		height: 240px;
		transition: transform 0.1s;
	}

	/* 摇晃动画 */
	.gashapon-machine.shaking {
		animation: shake 0.1s infinite;
	}

	@keyframes shake {
		0%, 100% { transform: translateX(0) rotate(0deg); }
		25% { transform: translateX(-3px) rotate(-2deg); }
		75% { transform: translateX(3px) rotate(2deg); }
	}

	/* 玻璃球容器 */
	.machine-globe {
		position: relative;
		width: 180px;
		height: 180px;
		background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(240, 240, 255, 0.8) 100%);
		border-radius: 50%;
		border: 4px solid #ff6b9d;
		box-shadow:
			inset 0 -20px 40px rgba(255, 107, 157, 0.2),
			0 8px 20px rgba(255, 107, 157, 0.3);
		overflow: hidden;
	}

	/* 玻璃反光效果 */
	.glass-shine {
		position: absolute;
		top: 15%;
		left: 20%;
		width: 40px;
		height: 60px;
		background: linear-gradient(135deg, rgba(255, 255, 255, 0.6), transparent);
		border-radius: 50%;
		transform: rotate(-30deg);
	}

	/* 扭蛋容器 */
	.capsules-container {
		position: absolute;
		width: 100%;
		height: 100%;
	}

	/* 小扭蛋 */
	.capsule-mini {
		position: absolute;
		width: 24px;
		height: 30px;
		border-radius: 50%;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
	}

	/* 底座 */
	.machine-base {
		position: relative;
		width: 160px;
		height: 60px;
		margin: 0 auto;
		background: linear-gradient(180deg, #ff6b9d 0%, #ff527a 100%);
		border-radius: 0 0 20px 20px;
		box-shadow: 0 4px 12px rgba(255, 107, 157, 0.4);
	}

	/* 出口 */
	.machine-opening {
		position: absolute;
		bottom: 8px;
		left: 50%;
		transform: translateX(-50%);
		width: 50px;
		height: 15px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 8px;
	}

	/* 旋钮 */
	.machine-knob {
		position: absolute;
		right: -10px;
		top: 140px;
		width: 35px;
		height: 35px;
		background: linear-gradient(135deg, #ffd93d 0%, #ffb800 100%);
		border-radius: 50%;
		border: 3px solid #ff8c00;
		box-shadow: 0 3px 8px rgba(255, 140, 0, 0.4);
	}

	/* 掉落的扭蛋 */
	.falling-capsule {
		position: absolute;
		width: 50px;
		height: 60px;
		top: 200px;
		left: 50%;
		transform: translateX(-50%);
	}

	.falling-capsule.falling {
		animation: fall 0.6s ease-in forwards;
	}

	@keyframes fall {
		0% {
			top: 160px;
			opacity: 1;
		}
		100% {
			top: 250px;
			opacity: 1;
		}
	}

	/* 扭蛋两半 */
	.capsule-half {
		position: absolute;
		width: 50px;
		height: 30px;
		border-radius: 25px 25px 0 0;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
	}

	.capsule-top {
		top: 0;
		background: linear-gradient(135deg, #ff6b9d 0%, #c94b7f 100%);
		z-index: 2;
	}

	.capsule-bottom {
		bottom: 0;
		background: linear-gradient(135deg, #ffd93d 0%, #ffb800 100%);
		border-radius: 0 0 25px 25px;
		z-index: 1;
	}

	/* 扭蛋打开动画 */
	.falling-capsule.opening .capsule-top {
		animation: openTop 0.4s ease-out forwards;
	}

	.falling-capsule.opening .capsule-bottom {
		animation: openBottom 0.4s ease-out forwards;
	}

	@keyframes openTop {
		0% {
			transform: translateY(0) rotate(0deg);
			opacity: 1;
		}
		100% {
			transform: translateY(-30px) rotate(-20deg);
			opacity: 0;
		}
	}

	@keyframes openBottom {
		0% {
			transform: translateY(0) rotate(0deg);
			opacity: 1;
		}
		100% {
			transform: translateY(30px) rotate(20deg);
			opacity: 0;
		}
	}

	/* 金币 */
	.coin {
		position: absolute;
		font-size: 24px;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		opacity: 0;
	}

	.coin-1 {
		animation: flyOut1 0.6s ease-out;
	}

	.coin-2 {
		animation: flyOut2 0.6s ease-out 0.1s;
	}

	.coin-3 {
		animation: flyOut3 0.6s ease-out 0.2s;
	}

	.coin-4 {
		animation: flyOut4 0.6s ease-out 0.15s;
	}

	.coin-5 {
		animation: flyOut5 0.6s ease-out 0.25s;
	}

	@keyframes flyOut1 {
		0% {
			transform: translate(-50%, -50%) scale(0);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(-80px, -60px) scale(1.2);
			opacity: 0;
		}
	}

	@keyframes flyOut2 {
		0% {
			transform: translate(-50%, -50%) scale(0);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(80px, -70px) scale(1.2);
			opacity: 0;
		}
	}

	@keyframes flyOut3 {
		0% {
			transform: translate(-50%, -50%) scale(0);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(0px, -90px) scale(1.2);
			opacity: 0;
		}
	}

	@keyframes flyOut4 {
		0% {
			transform: translate(-50%, -50%) scale(0);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(-60px, -80px) scale(1);
			opacity: 0;
		}
	}

	@keyframes flyOut5 {
		0% {
			transform: translate(-50%, -50%) scale(0);
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			transform: translate(60px, -85px) scale(1);
			opacity: 0;
		}
	}

	/* 奖励弹窗动画 */
	.animate-bounce {
		animation: modalBounce 0.5s ease-in-out 2;
	}

	@keyframes modalBounce {
		0%, 100% {
			transform: translateY(0);
		}
		50% {
			transform: translateY(-20px);
		}
	}
</style>

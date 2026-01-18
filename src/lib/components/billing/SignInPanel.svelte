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
	let diceRolling = false;
	let reward: number | null = null;
	let showReward = false;

	// 色子动画
	let diceValue = 1;
	let diceRotation = 0;

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
		diceRolling = true;
		reward = null;
		showReward = false;

		// 开始色子动画
		const rollInterval = setInterval(() => {
			diceValue = Math.floor(Math.random() * 6) + 1;
			diceRotation = Math.random() * 360;
		}, 100);

		try {
			// 等待动画持续一段时间（1.5秒）
			await new Promise((resolve) => setTimeout(resolve, 1500));

			// 执行签到 API 调用
			const response = await signIn(localStorage.token);

			// 停止色子动画
			clearInterval(rollInterval);
			diceRolling = false;

			// 设置最终奖励
			reward = response.amount;
			showReward = true;

			// 重新加载状态
			await loadStatus();

			// 显示成功消息
			toast.success(response.message);
		} catch (error: any) {
			clearInterval(rollInterval);
			diceRolling = false;
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
				<p class="text-sm text-gray-600 dark:text-gray-300">
					每天签到领取随机奖励哦~
				</p>
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
							<div class="text-2xl font-bold text-green-600 dark:text-green-400">
								¥{status.total_amount.toFixed(2)}
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">
								累计奖励
							</div>
						</div>
					</div>
				</div>

				<!-- 色子和签到按钮 -->
				<div class="text-center">
					{#if diceRolling}
						<!-- 色子动画 -->
						<div class="mb-6 flex items-center justify-center">
							<div
								class="text-8xl transform transition-transform duration-100"
								style="transform: rotate({diceRotation}deg);"
							>
								{#if diceValue === 1}🎲{:else if diceValue === 2}🎲{:else if diceValue === 3}🎲{:else if diceValue === 4}🎲{:else if diceValue === 5}🎲{:else}🎲{/if}
							</div>
						</div>
					{:else if status.has_signed_today}
						<!-- 已签到 -->
						<div class="mb-4">
							<div class="text-6xl mb-3">✅</div>
							<p class="text-lg font-semibold text-gray-700 dark:text-gray-300">
								今天已经签到啦~
							</p>
							<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
								明天再来吧！
							</p>
						</div>
					{:else}
						<!-- 未签到 - 显示色子 -->
						<div class="mb-4">
							<div class="text-7xl mb-3 hover:scale-110 transition-transform cursor-pointer" on:click={handleSignIn}>
								🎲
							</div>
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
									掷色子中...
								</span>
							{:else}
								🎉 点击签到
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
	@keyframes bounce {
		0%, 100% {
			transform: translateY(0);
		}
		50% {
			transform: translateY(-20px);
		}
	}

	.animate-bounce {
		animation: bounce 0.5s ease-in-out 2;
	}
</style>

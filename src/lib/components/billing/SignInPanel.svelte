<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		signIn,
		getSignInStatus,
		getPublicConfig,
		getSignInLogs,
		type SignInStatus,
		type SignInLog
	} from '$lib/apis/sign-in';
	import Spinner from '$lib/components/common/Spinner.svelte';

	// 签到状态
	let status: SignInStatus | null = null;
	let statusLoading = true;
	let isEnabled = false;

	// 签到记录
	let signInLogs: SignInLog[] = [];

	// 签到动画状态
	let isSigningIn = false;
	let reward: number | null = null;
	let showReward = false;
	let displayReward = 0;

	// 日历相关
	let currentMonth = new Date();

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

	// 加载签到记录
	const loadSignInLogs = async () => {
		try {
			// 获取最近90天的签到记录，足够显示3个月
			signInLogs = await getSignInLogs(localStorage.token, 90, 0);
		} catch (error) {
			console.error('加载签到记录失败:', error);
			signInLogs = [];
		}
	};

	// 执行签到
	const handleSignIn = async () => {
		if (!status || status.has_signed_today) return;

		isSigningIn = true;
		reward = null;
		showReward = false;
		displayReward = 0;

		try {
			const response = await signIn(localStorage.token);
			reward = response.amount;

			// 数字滚动动画
			const duration = 1000;
			const steps = 30;
			const increment = reward / steps;
			let currentStep = 0;

			const interval = setInterval(() => {
				currentStep++;
				displayReward = Math.min(currentStep * increment, reward);
				if (currentStep >= steps) {
					clearInterval(interval);
					displayReward = reward;
				}
			}, duration / steps);

			await loadStatus();
			await loadSignInLogs();
			toast.success(response.message);
		} catch (error: any) {
			toast.error(error || '签到失败，请稍后重试');
		} finally {
			isSigningIn = false;
		}
	};

	// 关闭奖励显示
	const closeReward = () => {
		showReward = false;
		reward = null;
		displayReward = 0;
	};

	// 生成日历数据
	$: calendarDays = generateCalendar(currentMonth);

	function generateCalendar(month: Date) {
		const year = month.getFullYear();
		const monthIndex = month.getMonth();
		const firstDay = new Date(year, monthIndex, 1);
		const lastDay = new Date(year, monthIndex + 1, 0);
		const startWeekday = firstDay.getDay();
		const daysInMonth = lastDay.getDate();

		const days = [];
		for (let i = 0; i < startWeekday; i++) {
			days.push(null);
		}
		for (let i = 1; i <= daysInMonth; i++) {
			days.push(i);
		}
		return days;
	}

	// 获取当月签到日期
	$: signedDates = getSignedDatesInMonth(currentMonth, signInLogs);

	function getSignedDatesInMonth(month: Date, logs: SignInLog[]): Set<number> {
		const dates = new Set<number>();
		const year = month.getFullYear();
		const monthIndex = month.getMonth();

		for (const log of logs) {
			// sign_in_date 格式为 "YYYY-MM-DD"
			const [logYear, logMonth, logDay] = log.sign_in_date.split('-').map(Number);
			if (logYear === year && logMonth === monthIndex + 1) {
				dates.add(logDay);
			}
		}

		return dates;
	}

	const prevMonth = () => {
		currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
	};

	const nextMonth = () => {
		currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
	};

	onMount(async () => {
		await loadPublicConfig();
		if (isEnabled) {
			await loadStatus();
			await loadSignInLogs();
		}
	});
</script>

{#if isEnabled}
	<div class="relative bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4 shadow-sm">
		{#if statusLoading}
			<div class="flex items-center justify-center py-8">
				<Spinner className="size-8" />
			</div>
		{:else if status}
			<!-- 标题和月份切换 -->
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-lg font-bold text-gray-900 dark:text-white">每日签到</h3>
				<div class="flex items-center gap-2">
					<button
						on:click={prevMonth}
						class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition"
						aria-label="上个月"
					>
						<svg class="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
						</svg>
					</button>
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300 min-w-[60px] text-center">
						{currentMonth.getMonth() + 1}月
					</span>
					<button
						on:click={nextMonth}
						class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition"
						aria-label="下个月"
					>
						<svg class="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
						</svg>
					</button>
				</div>
			</div>

			<!-- 星期标题 -->
			<div class="grid grid-cols-7 gap-1 mb-2">
				{#each ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as day}
					<div class="text-center text-xs text-gray-400 dark:text-gray-500 py-1 font-medium">
						{day}
					</div>
				{/each}
			</div>

			<!-- 日历格子 -->
			<div class="grid grid-cols-7 gap-1 mb-4">
				{#each calendarDays as day}
					{#if day === null}
						<div class="aspect-square"></div>
					{:else}
						{@const today = new Date()}
						{@const isToday = day === today.getDate() &&
						                  currentMonth.getMonth() === today.getMonth() &&
						                  currentMonth.getFullYear() === today.getFullYear()}
						{@const isSigned = signedDates.has(day)}
						<div class="aspect-square flex items-center justify-center relative">
							<span class="text-sm font-medium {isToday ? 'text-white z-10' : isSigned ? 'text-gray-900 dark:text-white' : 'text-gray-400 dark:text-gray-500'}">
								{day}
							</span>
							{#if isToday}
								<div class="absolute inset-0 bg-green-500 rounded-full -z-0 m-0.5"></div>
							{:else if isSigned}
								<div class="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 bg-black dark:bg-white rounded-full"></div>
							{/if}
						</div>
					{/if}
				{/each}
			</div>

			<!-- 底部信息和按钮 -->
			<div class="flex gap-2">
				<!-- 累计奖励 -->
				<div class="flex-1 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
					<div class="text-xs text-orange-600 dark:text-orange-400 mb-1 font-medium">累计奖励</div>
					<div class="flex items-center gap-1.5 text-orange-600 dark:text-orange-400">
						<span class="text-lg">💰</span>
						<div class="text-base font-bold tabular-nums">
							¥{status.total_amount.toFixed(2)}
						</div>
					</div>
				</div>

				<!-- 签到按钮 -->
				<div class="flex-1 border-2 border-orange-500 dark:border-orange-600 rounded-lg p-3 flex items-center justify-center">
					{#if status.has_signed_today && reward !== null}
						<div class="text-center">
							<div class="text-xs font-medium text-orange-600 dark:text-orange-400 mb-0.5">今日奖励</div>
							<div class="text-lg font-bold text-orange-600 dark:text-orange-400 tabular-nums">
								{displayReward.toFixed(2)}元
							</div>
						</div>
					{:else if status.has_signed_today}
						<div class="text-center">
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-0.5">今日奖励</div>
							<div class="text-lg font-bold text-gray-500 dark:text-gray-400">
								已领取
							</div>
						</div>
					{:else}
						<button
							on:click={handleSignIn}
							disabled={isSigningIn}
							class="text-orange-600 dark:text-orange-400 font-bold text-base hover:text-orange-700 dark:hover:text-orange-300 disabled:opacity-50 transition"
						>
							{isSigningIn ? '签到中...' : '点击签到'}
						</button>
					{/if}
				</div>
			</div>
		{/if}
	</div>

	<!-- 奖励弹窗 -->
	{#if showReward && reward !== null}
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" on:click={closeReward}>
			<div class="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-2xl max-w-sm mx-4 relative" on:click|stopPropagation>
				<button
					class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
					on:click={closeReward}
				>
					<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>

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
						class="px-6 py-2 bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700 text-white font-medium rounded-full transition"
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
	/* 数字滚动动画 */
	.tabular-nums {
		font-variant-numeric: tabular-nums;
	}
</style>

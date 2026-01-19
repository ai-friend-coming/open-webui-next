<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import {
		getFirstRechargeBonusConfig,
		updateFirstRechargeBonusConfig,
		getFirstRechargeBonusStats,
		getFirstRechargeBonusParticipants,
		type FirstRechargeBonusConfig,
		type FirstRechargeBonusStats,
		type ParticipantItem
	} from '$lib/apis/first-recharge-bonus';
	import { getRechargeTiers } from '$lib/apis/configs';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	// 配置
	let config: FirstRechargeBonusConfig = {
		enabled: false,
		rate: 10,
		max_amount: 50
	};
	let configLoading = false;
	let configSaving = false;

	// 统计
	let stats: FirstRechargeBonusStats = {
		participant_count: 0,
		total_recharge: 0,
		total_bonus: 0
	};
	let statsLoading = false;

	// 参与者列表
	let participants: ParticipantItem[] = [];
	let participantsTotal = 0;
	let participantsLoading = false;
	let currentPage = 0;
	let pageSize = 50;

	// 充值档位
	let rechargeTiers: number[] = [];
	let tiersLoading = false;

	// 加载配置
	const loadConfig = async () => {
		configLoading = true;
		try {
			config = await getFirstRechargeBonusConfig(localStorage.token);
		} catch (error) {
			toast.error(`加载配置失败: ${error}`);
		} finally {
			configLoading = false;
		}
	};

	// 保存配置
	const saveConfig = async () => {
		configSaving = true;
		try {
			config = await updateFirstRechargeBonusConfig(localStorage.token, config);
			toast.success('配置保存成功');
			// 重新加载统计
			await loadStats();
		} catch (error) {
			toast.error(`保存配置失败: ${error}`);
		} finally {
			configSaving = false;
		}
	};

	// 加载统计
	const loadStats = async () => {
		statsLoading = true;
		try {
			stats = await getFirstRechargeBonusStats(localStorage.token);
		} catch (error) {
			toast.error(`加载统计失败: ${error}`);
		} finally {
			statsLoading = false;
		}
	};

	// 加载参与者列表
	const loadParticipants = async () => {
		participantsLoading = true;
		try {
			const res = await getFirstRechargeBonusParticipants(
				localStorage.token,
				pageSize,
				currentPage * pageSize
			);
			participants = res.participants;
			participantsTotal = res.total;
		} catch (error) {
			toast.error(`加载参与者列表失败: ${error}`);
		} finally {
			participantsLoading = false;
		}
	};

	// 加载充值档位
	const loadTiers = async () => {
		tiersLoading = true;
		try {
			rechargeTiers = await getRechargeTiers(localStorage.token);
		} catch (error) {
			toast.error(`加载充值档位失败: ${error}`);
		} finally {
			tiersLoading = false;
		}
	};

	// 分页变化时重新加载
	$: if (currentPage !== undefined) {
		loadParticipants();
	}

	// 格式化时间（纳秒时间戳）
	const formatTime = (nanoseconds: number) => {
		// 转换为毫秒
		const milliseconds = nanoseconds / 1000000;
		return dayjs(milliseconds).format('YYYY-MM-DD HH:mm:ss');
	};

	onMount(() => {
		loadConfig();
		loadStats();
		loadParticipants();
		loadTiers();
	});
</script>

<div class="flex flex-col h-full">
	<!-- 标题 -->
	<div class="mb-6">
		<h2 class="text-xl font-semibold text-gray-900 dark:text-white">首充优惠活动</h2>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
			配置首次充值优惠活动，新用户首次充值可获得额外奖励
		</p>
	</div>

	<!-- 活动配置 -->
	<div class="mb-6 p-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
		<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">活动配置</h3>

		{#if configLoading}
			<div class="flex items-center justify-center py-8">
				<Spinner className="size-8" />
			</div>
		{:else}
			<div class="space-y-4">
				<!-- 启用开关 -->
				<div class="flex items-center justify-between">
					<div>
						<label class="text-sm font-medium text-gray-700 dark:text-gray-300">启用活动</label>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							启用后，用户首次充值将自动获得奖励
						</p>
					</div>
					<label class="relative inline-flex items-center cursor-pointer">
						<input type="checkbox" bind:checked={config.enabled} class="sr-only peer" />
						<div
							class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"
						></div>
					</label>
				</div>

				<!-- 返现比例 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						返现比例（%）
					</label>
					<input
						type="number"
						bind:value={config.rate}
						min="0"
						max="100"
						step="0.1"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						例如：设置 10 表示返现 10%
					</p>
				</div>

				<!-- 返现上限 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						最高返现金额（元）
					</label>
					<input
						type="number"
						bind:value={config.max_amount}
						min="0"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						例如：设置 50 表示最高返现 50 元
					</p>
				</div>

				<!-- 可用充值档位 -->
				<div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
					<div class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
						当前充值档位
					</div>
					{#if tiersLoading}
						<div class="flex items-center gap-2">
							<Spinner className="size-4" />
							<span class="text-xs text-gray-500 dark:text-gray-400">加载中...</span>
						</div>
					{:else if rechargeTiers.length > 0}
						<div class="flex flex-wrap gap-2">
							{#each rechargeTiers as tier}
								<div class="px-3 py-1 bg-white dark:bg-gray-800 rounded-md border border-blue-200 dark:border-blue-800">
									<span class="text-sm font-mono text-gray-900 dark:text-gray-100">{tier}</span>
									<span class="text-xs text-gray-600 dark:text-gray-400 ml-1">元</span>
								</div>
							{/each}
						</div>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
							首充优惠仅对以上档位金额生效，其他金额不参与活动
						</p>
					{:else}
						<p class="text-xs text-gray-500 dark:text-gray-400">
							未配置充值档位，请前往"充值档位"设置页面配置
						</p>
					{/if}
				</div>

				<!-- 保存按钮 -->
				<div class="pt-2">
					<button
						class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
						on:click={saveConfig}
						disabled={configSaving}
					>
						{#if configSaving}
							<Spinner className="size-4" />
							保存中...
						{:else}
							保存配置
						{/if}
					</button>
				</div>
			</div>
		{/if}
	</div>

	<!-- 统计卡片 -->
	<div class="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
		<!-- 参与人数 -->
		<div class="p-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
			<div class="flex items-center justify-between">
				<div>
					<p class="text-sm font-medium text-gray-500 dark:text-gray-400">参与人数</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-white mt-2">
						{statsLoading ? '-' : stats.participant_count}
					</p>
				</div>
				<div class="p-3 bg-blue-100 dark:bg-blue-900/20 rounded-lg">
					<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
					</svg>
				</div>
			</div>
		</div>

		<!-- 总充值金额 -->
		<div class="p-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
			<div class="flex items-center justify-between">
				<div>
					<p class="text-sm font-medium text-gray-500 dark:text-gray-400">总充值金额</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-white mt-2">
						¥{statsLoading ? '-' : stats.total_recharge.toFixed(2)}
					</p>
				</div>
				<div class="p-3 bg-green-100 dark:bg-green-900/20 rounded-lg">
					<svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
					</svg>
				</div>
			</div>
		</div>

		<!-- 总奖励金额 -->
		<div class="p-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
			<div class="flex items-center justify-between">
				<div>
					<p class="text-sm font-medium text-gray-500 dark:text-gray-400">总奖励金额</p>
					<p class="text-2xl font-bold text-gray-900 dark:text-white mt-2">
						¥{statsLoading ? '-' : stats.total_bonus.toFixed(2)}
					</p>
				</div>
				<div class="p-3 bg-orange-100 dark:bg-orange-900/20 rounded-lg">
					<svg class="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7" />
					</svg>
				</div>
			</div>
		</div>
	</div>

	<!-- 参与者列表 -->
	<div class="flex-1 flex flex-col">
		<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">参与者列表</h3>

		<div class="flex-1 overflow-auto border border-gray-200 dark:border-gray-700 rounded-lg">
			{#if participantsLoading}
				<div class="flex items-center justify-center h-64">
					<Spinner className="size-8" />
				</div>
			{:else if participants.length === 0}
				<div class="flex flex-col items-center justify-center h-64 text-gray-400">
					<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
					</svg>
					<p class="text-lg font-medium">暂无参与者</p>
					<p class="text-sm mt-1">还没有用户参与首充优惠活动</p>
				</div>
			{:else}
				<table class="w-full">
					<thead class="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">用户</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">充值金额</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">奖励金额</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">返现比例</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">参与时间</th>
						</tr>
					</thead>
					<tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
						{#each participants as participant (participant.id)}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
								<!-- 用户 -->
								<td class="px-4 py-3">
									<div>
										<div class="text-sm font-medium text-gray-900 dark:text-white">
											{participant.user_name}
										</div>
										{#if participant.user_email}
											<div class="text-xs text-gray-500 dark:text-gray-400">
												{participant.user_email}
											</div>
										{/if}
									</div>
								</td>

								<!-- 充值金额 -->
								<td class="px-4 py-3">
									<span class="text-sm font-medium text-gray-900 dark:text-white">
										¥{participant.recharge_amount.toFixed(2)}
									</span>
								</td>

								<!-- 奖励金额 -->
								<td class="px-4 py-3">
									<span class="text-sm font-medium text-green-600">
										¥{participant.bonus_amount.toFixed(2)}
									</span>
								</td>

								<!-- 返现比例 -->
								<td class="px-4 py-3">
									<span class="text-sm text-gray-700 dark:text-gray-300">
										{participant.bonus_rate}%
									</span>
								</td>

								<!-- 参与时间 -->
								<td class="px-4 py-3">
									<span class="text-sm text-gray-500 dark:text-gray-400">
										{formatTime(participant.created_at)}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>

		<!-- 分页 -->
		{#if participantsTotal > pageSize}
			<div class="flex items-center justify-between mt-4 px-4">
				<div class="text-sm text-gray-500 dark:text-gray-400">
					显示 {currentPage * pageSize + 1} - {Math.min((currentPage + 1) * pageSize, participantsTotal)} / 共 {participantsTotal} 条
				</div>
				<div class="flex items-center gap-2">
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						disabled={currentPage === 0}
						on:click={() => (currentPage = 0)}
					>
						首页
					</button>
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						disabled={currentPage === 0}
						on:click={() => currentPage--}
					>
						上一页
					</button>
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						disabled={(currentPage + 1) * pageSize >= participantsTotal}
						on:click={() => currentPage++}
					>
						下一页
					</button>
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						disabled={(currentPage + 1) * pageSize >= participantsTotal}
						on:click={() => (currentPage = Math.floor(participantsTotal / pageSize))}
					>
						末页
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

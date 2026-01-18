<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import {
		getSignInConfig,
		updateSignInConfig,
		getSignInLogs,
		type SignInConfig,
		type SignInLog
	} from '$lib/apis/sign-in';

	import Spinner from '$lib/components/common/Spinner.svelte';

	// 配置
	let config: SignInConfig = {
		enabled: false,
		mean: 1.0,
		std: 0.5,
		min_amount: 0.1,
		max_amount: 5.0
	};
	let configLoading = false;
	let configSaving = false;

	// 签到记录
	let logs: SignInLog[] = [];
	let logsLoading = false;
	let currentPage = 0;
	let pageSize = 20;

	// 加载配置
	const loadConfig = async () => {
		configLoading = true;
		try {
			config = await getSignInConfig(localStorage.token);
		} catch (error) {
			toast.error(`加载配置失败: ${error}`);
		} finally {
			configLoading = false;
		}
	};

	// 保存配置
	const saveConfig = async () => {
		// 验证配置
		if (config.min_amount > config.max_amount) {
			toast.error('最小金额不能大于最大金额');
			return;
		}

		if (config.std < 0) {
			toast.error('标准差必须大于等于 0');
			return;
		}

		configSaving = true;
		try {
			config = await updateSignInConfig(localStorage.token, config);
			toast.success('配置保存成功');
		} catch (error) {
			toast.error(`保存配置失败: ${error}`);
		} finally {
			configSaving = false;
		}
	};

	// 加载签到记录
	const loadLogs = async () => {
		logsLoading = true;
		try {
			logs = await getSignInLogs(localStorage.token, pageSize, currentPage * pageSize);
		} catch (error) {
			toast.error(`加载签到记录失败: ${error}`);
		} finally {
			logsLoading = false;
		}
	};

	// 分页变化时重新加载
	$: if (currentPage !== undefined) {
		loadLogs();
	}

	// 格式化时间（纳秒时间戳）
	const formatTime = (nanoseconds: number) => {
		// 转换为毫秒
		const milliseconds = nanoseconds / 1000000;
		return dayjs(milliseconds).format('YYYY-MM-DD HH:mm:ss');
	};

	onMount(() => {
		loadConfig();
		loadLogs();
	});
</script>

<div class="flex flex-col h-full">
	<!-- 标题 -->
	<div class="mb-6">
		<h2 class="text-xl font-semibold text-gray-900 dark:text-white">每日签到系统</h2>
		<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
			配置每日签到奖励系统，用户每天签到可获得随机金额奖励
		</p>
	</div>

	<!-- 签到配置 -->
	<div class="mb-6 p-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
		<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">签到配置</h3>

		{#if configLoading}
			<div class="flex items-center justify-center py-8">
				<Spinner className="size-8" />
			</div>
		{:else}
			<div class="space-y-4">
				<!-- 启用开关 -->
				<div class="flex items-center justify-between">
					<div>
						<label class="text-sm font-medium text-gray-700 dark:text-gray-300">启用签到</label>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
							启用后，用户每天可以签到一次并获得奖励
						</p>
					</div>
					<label class="relative inline-flex items-center cursor-pointer">
						<input type="checkbox" bind:checked={config.enabled} class="sr-only peer" />
						<div
							class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"
						></div>
					</label>
				</div>

				<!-- 奖励金额分布说明 -->
				<div class="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
					<h4 class="text-sm font-medium text-blue-900 dark:text-blue-300 mb-2">
						💡 奖励金额分布原理
					</h4>
					<p class="text-xs text-blue-800 dark:text-blue-400">
						签到奖励金额遵循<strong>正态分布（高斯分布）</strong>，大部分用户会获得接近均值的奖励，少数用户会获得较高或较低的奖励。
					</p>
					<ul class="mt-2 text-xs text-blue-800 dark:text-blue-400 list-disc list-inside space-y-1">
						<li><strong>均值</strong>：奖励金额的中心值，最常见的奖励金额</li>
						<li><strong>标准差</strong>：控制奖励金额的波动范围，值越大波动越大</li>
						<li><strong>最小/最大金额</strong>：限制奖励金额的边界</li>
					</ul>
				</div>

				<!-- 均值 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						奖励金额均值（元）
					</label>
					<input
						type="number"
						bind:value={config.mean}
						min="0"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						例如：设置 1.0 表示平均每次签到获得 1.0 元
					</p>
				</div>

				<!-- 标准差 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						标准差（元）
					</label>
					<input
						type="number"
						bind:value={config.std}
						min="0"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						例如：设置 0.5 表示大约 68% 的奖励会在 [均值-0.5, 均值+0.5] 范围内
					</p>
				</div>

				<!-- 最小金额 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						最小奖励金额（元）
					</label>
					<input
						type="number"
						bind:value={config.min_amount}
						min="0"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						任何签到奖励不会低于此金额
					</p>
				</div>

				<!-- 最大金额 -->
				<div>
					<label class="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">
						最大奖励金额（元）
					</label>
					<input
						type="number"
						bind:value={config.max_amount}
						min="0"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
						任何签到奖励不会高于此金额
					</p>
				</div>

				<!-- 预览示例 -->
				<div class="p-4 bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg">
					<h4 class="text-sm font-medium text-gray-900 dark:text-white mb-2">
						📊 预期奖励分布
					</h4>
					<div class="grid grid-cols-3 gap-4 text-sm">
						<div>
							<p class="text-gray-500 dark:text-gray-400">68% 用户获得</p>
							<p class="font-medium text-gray-900 dark:text-white">
								¥{Math.max(config.min_amount, config.mean - config.std).toFixed(2)} - ¥{Math.min(config.max_amount, config.mean + config.std).toFixed(2)}
							</p>
						</div>
						<div>
							<p class="text-gray-500 dark:text-gray-400">95% 用户获得</p>
							<p class="font-medium text-gray-900 dark:text-white">
								¥{Math.max(config.min_amount, config.mean - 2 * config.std).toFixed(2)} - ¥{Math.min(config.max_amount, config.mean + 2 * config.std).toFixed(2)}
							</p>
						</div>
						<div>
							<p class="text-gray-500 dark:text-gray-400">边界范围</p>
							<p class="font-medium text-gray-900 dark:text-white">
								¥{config.min_amount.toFixed(2)} - ¥{config.max_amount.toFixed(2)}
							</p>
						</div>
					</div>
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

	<!-- 最近签到记录 -->
	<div class="flex-1 flex flex-col">
		<h3 class="text-lg font-medium text-gray-900 dark:text-white mb-4">最近签到记录</h3>

		<div class="flex-1 overflow-auto border border-gray-200 dark:border-gray-700 rounded-lg">
			{#if logsLoading}
				<div class="flex items-center justify-center h-64">
					<Spinner className="size-8" />
				</div>
			{:else if logs.length === 0}
				<div class="flex flex-col items-center justify-center h-64 text-gray-400">
					<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
					</svg>
					<p class="text-lg font-medium">暂无签到记录</p>
					<p class="text-sm mt-1">还没有用户签到</p>
				</div>
			{:else}
				<table class="w-full">
					<thead class="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0">
						<tr>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">签到日期</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">奖励金额</th>
							<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">签到时间</th>
						</tr>
					</thead>
					<tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
						{#each logs as log (log.id)}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
								<!-- 签到日期 -->
								<td class="px-4 py-3">
									<span class="text-sm font-medium text-gray-900 dark:text-white">
										{log.sign_in_date}
									</span>
								</td>

								<!-- 奖励金额 -->
								<td class="px-4 py-3">
									<span class="text-sm font-medium text-green-600">
										¥{log.amount.toFixed(2)}
									</span>
								</td>

								<!-- 签到时间 -->
								<td class="px-4 py-3">
									<span class="text-sm text-gray-500 dark:text-gray-400">
										{formatTime(log.created_at)}
									</span>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>

		<!-- 分页 -->
		{#if logs.length === pageSize}
			<div class="flex items-center justify-end mt-4 px-4">
				<div class="flex items-center gap-2">
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						disabled={currentPage === 0}
						on:click={() => currentPage--}
					>
						上一页
					</button>
					<span class="text-sm text-gray-500 dark:text-gray-400">
						第 {currentPage + 1} 页
					</span>
					<button
						class="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
						on:click={() => currentPage++}
					>
						下一页
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

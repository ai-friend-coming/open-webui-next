<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getRechargeTiers, setRechargeTiers } from '$lib/apis/configs';

	const i18n = getContext('i18n');

	let tiers: number[] = [];
	let newTierValue = '';
	let loading = false;
	let saving = false;

	onMount(async () => {
		await loadTiers();
	});

	async function loadTiers() {
		loading = true;
		try {
			const fetchedTiers = await getRechargeTiers(localStorage.token);
			tiers = fetchedTiers || [];
		} catch (error) {
			console.error('Failed to load recharge tiers:', error);
			toast.error($i18n.t('加载充值档位失败'));
		} finally {
			loading = false;
		}
	}

	function addTier() {
		const value = parseFloat(newTierValue);
		if (isNaN(value) || value < 0.01 || value > 100000) {
			toast.error($i18n.t('档位金额必须在 0.01-100000 元之间'));
			return;
		}

		if (tiers.includes(value)) {
			toast.error($i18n.t('该档位已存在'));
			return;
		}

		if (tiers.length >= 20) {
			toast.error($i18n.t('最多支持 20 个档位'));
			return;
		}

		tiers = [...tiers, value].sort((a, b) => a - b);
		newTierValue = '';
	}

	function removeTier(tier: number) {
		tiers = tiers.filter((t) => t !== tier);
	}

	async function saveTiers() {
		if (tiers.length === 0) {
			toast.error($i18n.t('至少需要一个充值档位'));
			return;
		}

		saving = true;
		try {
			await setRechargeTiers(localStorage.token, tiers);
			toast.success($i18n.t('充值档位配置已保存'));
		} catch (error) {
			console.error('Failed to save recharge tiers:', error);
			toast.error($i18n.t('保存失败'));
		} finally {
			saving = false;
		}
	}

	function handleKeyPress(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			addTier();
		}
	}
</script>

<div class="flex flex-col h-full justify-between text-sm">
	<div class="pr-1.5 space-y-2">
		<div>
			<div class="mb-1 text-sm font-medium">{$i18n.t('充值档位配置')}</div>

			<div class="flex flex-col gap-4">
				<!-- 添加档位 -->
				<div>
					<label class="flex items-center gap-2 mb-2">
						<span class="font-medium">{$i18n.t('添加档位')}:</span>
						<input
							bind:value={newTierValue}
							on:keypress={handleKeyPress}
							type="number"
							min="0.01"
							max="100000"
							step="0.01"
							placeholder="10"
							class="w-32 px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							disabled={loading || saving}
						/>
						<span class="text-gray-600 dark:text-gray-400">元</span>
						<button
							on:click={addTier}
							class="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition disabled:opacity-50"
							disabled={loading || saving || !newTierValue}
						>
							{$i18n.t('添加')}
						</button>
					</label>
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('充值档位范围：0.01 - 100000 元，最多 20 个档位')}
					</div>
				</div>

				<!-- 当前档位列表 -->
				<div>
					<div class="font-medium mb-2">{$i18n.t('当前档位')}:</div>
					{#if tiers.length === 0}
						<div class="text-gray-500 dark:text-gray-400 text-sm">
							{$i18n.t('暂无充值档位')}
						</div>
					{:else}
						<div class="flex flex-wrap gap-2">
							{#each tiers as tier}
								<div
									class="flex items-center gap-2 px-3 py-1 bg-gray-100 dark:bg-gray-800 rounded-md"
								>
									<span class="font-mono">{tier}</span>
									<span class="text-gray-600 dark:text-gray-400">元</span>
									<button
										on:click={() => removeTier(tier)}
										class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
										disabled={loading || saving}
									>
										<svg
											class="w-4 h-4"
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
									</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>

				<!-- 说明信息 -->
				<div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
					<div class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
						{$i18n.t('说明')}
					</div>
					<ul class="text-xs text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
						<li>{$i18n.t('充值档位决定用户可选择的充值金额')}</li>
						<li>{$i18n.t('档位变更后，前端充值选项会立即更新')}</li>
						<li>{$i18n.t('首充优惠仅针对档位内的充值金额生效')}</li>
						<li>{$i18n.t('建议设置常用的整数档位，如 10、50、100、500、1000 元')}</li>
					</ul>
				</div>
			</div>
		</div>
	</div>

	<div class="flex justify-end pt-3">
		<button
			class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
			on:click={saveTiers}
			disabled={loading || saving}
		>
			{saving ? $i18n.t('保存中...') : $i18n.t('保存')}
		</button>
	</div>
</div>

<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getInviteConfig, updateInviteConfig } from '$lib/apis/invite';

	const i18n = getContext('i18n');

	let rebateRate = 5;
	let loading = false;
	let saving = false;

	onMount(async () => {
		await loadConfig();
	});

	async function loadConfig() {
		loading = true;
		try {
			const config = await getInviteConfig();
			rebateRate = config.rebate_rate;
		} catch (error) {
			console.error('Failed to load invite config:', error);
			toast.error($i18n.t('加载配置失败'));
		} finally {
			loading = false;
		}
	}

	async function saveConfig() {
		if (rebateRate < 0 || rebateRate > 100) {
			toast.error($i18n.t('返现比例必须在 0-100 之间'));
			return;
		}

		saving = true;
		try {
			await updateInviteConfig(localStorage.token, rebateRate);
			toast.success($i18n.t('配置已保存'));
		} catch (error) {
			console.error('Failed to save invite config:', error);
			toast.error($i18n.t('保存失败'));
		} finally {
			saving = false;
		}
	}
</script>

<div class="flex flex-col h-full justify-between text-sm">
	<div class="  pr-1.5 space-y-2">
		<div>
			<div class=" mb-1 text-sm font-medium">{$i18n.t('邀请返现配置')}</div>

			<div class="flex flex-col gap-4">
				<!-- 返现比例设置 -->
				<div>
					<label class="flex items-center gap-2 mb-2">
						<span class="font-medium">{$i18n.t('返现比例')}:</span>
						<input
							bind:value={rebateRate}
							type="number"
							min="0"
							max="100"
							step="1"
							class="w-24 px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							disabled={loading || saving}
						/>
						<span class="text-gray-600 dark:text-gray-400">%</span>
					</label>
					<div class="text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('当被邀请用户充值时，邀请人获得充值金额的此比例作为返现')}
					</div>
				</div>

				<!-- 说明信息 -->
				<div class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
					<div class="text-sm font-medium text-blue-800 dark:text-blue-200 mb-2">
						{$i18n.t('邀请系统说明')}
					</div>
					<ul class="text-xs text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
						<li>{$i18n.t('每个用户注册时自动生成唯一邀请码')}</li>
						<li>{$i18n.t('新用户注册时可填写邀请码建立邀请关系')}</li>
						<li>{$i18n.t('被邀请用户每次充值，邀请人立即获得返现')}</li>
						<li>{$i18n.t('返现金额 = 充值金额 × 返现比例')}</li>
						<li>{$i18n.t('仅一级返现，不支持多级分销')}</li>
					</ul>
				</div>
			</div>
		</div>
	</div>

	<div class="flex justify-end pt-3">
		<button
			class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
			on:click={saveConfig}
			disabled={loading || saving}
		>
			{saving ? $i18n.t('保存中...') : $i18n.t('保存')}
		</button>
	</div>
</div>

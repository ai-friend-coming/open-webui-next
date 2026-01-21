<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { getInviteConfig, updateInviteConfig, getAllInviteRelationships, type InviteRelationshipsResponse } from '$lib/apis/invite';

	const i18n = getContext('i18n');

	let rebateRate = 5;
	let loading = false;
	let saving = false;
	let relationships: InviteRelationshipsResponse | null = null;
	let loadingRelationships = false;

	onMount(async () => {
		await loadConfig();
		await loadRelationships();
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

	async function loadRelationships() {
		loadingRelationships = true;
		try {
			relationships = await getAllInviteRelationships(localStorage.token);
		} catch (error) {
			console.error('Failed to load invite relationships:', error);
			toast.error($i18n.t('加载邀请关系失败'));
		} finally {
			loadingRelationships = false;
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

	function formatDate(timestamp: number) {
		return new Date(timestamp / 1000000).toLocaleDateString();
	}
</script>

<div class="flex flex-col h-full text-sm overflow-y-auto">
	<div class="pr-1.5 space-y-4">
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
						<li>{$i18n.t('邀请返现功能永久有效，无需额外开启')}</li>
						<li>{$i18n.t('每个用户注册时自动生成唯一邀请码')}</li>
						<li>{$i18n.t('新用户注册时可填写邀请码建立邀请关系')}</li>
						<li>{$i18n.t('被邀请用户每次充值，邀请人立即获得返现')}</li>
						<li>{$i18n.t('返现金额 = 充值金额 × 返现比例')}</li>
						<li>{$i18n.t('仅一级返现，不支持多级分销')}</li>
					</ul>
				</div>

				<div class="flex justify-end">
					<button
						class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-50"
						on:click={saveConfig}
						disabled={loading || saving}
					>
						{saving ? $i18n.t('保存中...') : $i18n.t('保存')}
					</button>
				</div>
			</div>
		</div>

		<!-- 邀请关系列表 -->
		<div class="mt-6">
			<div class="mb-3 flex items-center justify-between">
				<div class="text-sm font-medium">{$i18n.t('邀请关系')}</div>
				{#if relationships}
					<div class="text-xs text-gray-500">
						{$i18n.t('共')} {relationships.total_inviters} {$i18n.t('位邀请人')}, {relationships.total_invitees} {$i18n.t('位被邀请用户')}
					</div>
				{/if}
			</div>

			{#if loadingRelationships}
				<div class="text-center py-8 text-gray-500">
					{$i18n.t('加载中...')}
				</div>
			{:else if relationships && relationships.relationships.length > 0}
				<div class="space-y-4">
					{#each relationships.relationships as relationship}
						<div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
							<div class="flex items-center gap-2 mb-3">
								<div class="font-medium text-gray-900 dark:text-gray-100">
									{relationship.inviter.name}
								</div>
								<div class="text-xs text-gray-500">
									({relationship.inviter.email || relationship.inviter.id})
								</div>
								<div class="text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 px-2 py-0.5 rounded">
									{$i18n.t('邀请码')}: {relationship.inviter.invite_code}
								</div>
								<div class="text-xs text-gray-500 ml-auto">
									{$i18n.t('已邀请')} {relationship.invitees.length} {$i18n.t('人')}
								</div>
							</div>

							<div class="pl-4 border-l-2 border-gray-200 dark:border-gray-700 space-y-2">
								{#each relationship.invitees as invitee}
									<div class="flex items-center gap-2 text-sm">
										<div class="w-2 h-2 rounded-full bg-gray-400"></div>
										<div class="text-gray-700 dark:text-gray-300">
											{invitee.name}
										</div>
										<div class="text-xs text-gray-500">
											({invitee.email || invitee.id})
										</div>
										<div class="text-xs text-gray-400 ml-auto">
											{formatDate(invitee.created_at)}
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="text-center py-8 text-gray-500">
					{$i18n.t('暂无邀请关系')}
				</div>
			{/if}
		</div>
	</div>
</div>

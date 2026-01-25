<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	import { getBillingLogsByUserId, type BillingLog } from '$lib/apis/billing';
	import { formatCurrency, formatDate } from '$lib/stores';
	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let selectedUser: any;

	let logs: BillingLog[] = [];
	let loading = true;

	const loadLogs = async () => {
		if (!selectedUser?.id) return;

		loading = true;
		try {
			logs = await getBillingLogsByUserId(localStorage.token, selectedUser.id);
		} catch (error: any) {
			console.error('加载计费记录失败:', error);
			toast.error($i18n.t('加载计费记录失败') + ': ' + (error.detail || error));
		} finally {
			loading = false;
		}
	};

	$: if (show && selectedUser) {
		loadLogs();
	}

	const formatTokens = (value?: number | null) =>
		value === null || value === undefined ? '-' : value.toLocaleString();

	const formatCost = (value?: number | null) =>
		value === null || value === undefined ? '-' : formatCurrency(value, true);

	const formatBalance = (value?: number | null) =>
		value === null || value === undefined ? '-' : formatCurrency(value, false);

	const formatText = (value?: string | null) => value || '-';
</script>

<Modal size="xl" bind:show>
	<div class="flex flex-col max-h-[80vh]">
		<div class="flex justify-between dark:text-gray-300 px-5 pt-4 pb-2 shrink-0">
			<div class="text-lg font-medium self-center">
				{$i18n.t('计费记录')} - {selectedUser?.name}
			</div>
			<button
				class="self-center"
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="px-5 pb-5 overflow-y-auto min-h-0 flex-1">
			{#if loading}
				<div class="text-center py-8 dark:text-gray-400">
					{$i18n.t('加载中')}...
				</div>
			{:else if logs.length === 0}
				<div class="text-center py-8 text-gray-500 dark:text-gray-400">
					{$i18n.t('暂无计费记录')}
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-xs">
						<thead>
							<tr class="border-b dark:border-gray-700">
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('时间')}
								</th>
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('类型')}
								</th>
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('模型')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('输入Token')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('输出Token')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('预估Token')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('费用')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('余额')}
								</th>
								<th class="text-right py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('退款/补扣')}
								</th>
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('状态')}
								</th>
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('预扣ID')}
								</th>
								<th class="text-left py-2 px-2 font-medium dark:text-gray-300">
									{$i18n.t('记录ID')}
								</th>
							</tr>
						</thead>
						<tbody>
							{#each logs as log}
								<tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="py-2 px-2 dark:text-gray-300">
										{formatDate(log.created_at)}
									</td>
									<td class="py-2 px-2 dark:text-gray-300">
										{formatText(log.type)}
									</td>
									<td class="py-2 px-2 dark:text-gray-300">
										<code class="font-mono text-xs">{log.model_id}</code>
									</td>
									<td class="py-2 px-2 text-right dark:text-gray-300">
										{formatTokens(log.prompt_tokens)}
									</td>
									<td class="py-2 px-2 text-right dark:text-gray-300">
										{formatTokens(log.completion_tokens)}
									</td>
									<td class="py-2 px-2 text-right dark:text-gray-300">
										{formatTokens(log.estimated_tokens)}
									</td>
									<td class="py-2 px-2 text-right font-medium dark:text-gray-300">
										{formatCost(log.cost)}
									</td>
									<td class="py-2 px-2 text-right dark:text-gray-300">
										{formatBalance(log.balance_after)}
									</td>
									<td class="py-2 px-2 text-right dark:text-gray-300">
										{formatCost(log.refund_amount)}
									</td>
									<td class="py-2 px-2 dark:text-gray-300">
										{formatText(log.status)}
									</td>
									<td class="py-2 px-2 dark:text-gray-300">
										<code class="font-mono text-xs break-all">
											{formatText(log.precharge_id)}
										</code>
									</td>
									<td class="py-2 px-2 dark:text-gray-300">
										<code class="font-mono text-xs break-all">{log.id}</code>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
</Modal>

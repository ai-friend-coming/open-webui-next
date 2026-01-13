<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import {
		listRedeemCodes,
		deleteRedeemCode,
		toggleRedeemCode,
		formatStatus,
		getStatusColor,
		type RedeemCode
	} from '$lib/apis/redeem-codes';

	import CreateRedeemCodeModal from './RedeemCodes/CreateRedeemCodeModal.svelte';
	import EditRedeemCodeModal from './RedeemCodes/EditRedeemCodeModal.svelte';
	import RedeemCodeLogsModal from './RedeemCodes/RedeemCodeLogsModal.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	let codes: RedeemCode[] = [];
	let total = 0;
	let loading = false;
	let selectedCode: RedeemCode | null = null;

	// 模态框状态
	let showCreateModal = false;
	let showEditModal = false;
	let showLogsModal = false;
	let showDeleteConfirm = false;

	// 筛选和分页
	let statusFilter = 'all';
	let currentPage = 0;
	let pageSize = 50;

	// 加载兑换码列表
	const loadCodes = async () => {
		loading = true;
		try {
			const res = await listRedeemCodes(
				localStorage.token,
				statusFilter,
				currentPage * pageSize,
				pageSize
			);
			codes = res.codes;
			total = res.total;
		} catch (error) {
			toast.error(`加载失败: ${error}`);
		} finally {
			loading = false;
		}
	};

	// 复制兑换码
	const copyCode = async (code: string) => {
		try {
			await navigator.clipboard.writeText(code);
			toast.success('兑换码已复制');
		} catch (error) {
			toast.error('复制失败');
		}
	};

	// 启用/禁用
	const handleToggle = async (codeId: string) => {
		try {
			await toggleRedeemCode(localStorage.token, codeId);
			toast.success('操作成功');
			await loadCodes();
		} catch (error) {
			toast.error(`操作失败: ${error}`);
		}
	};

	// 删除
	const handleDelete = async () => {
		if (!selectedCode) return;

		try {
			await deleteRedeemCode(localStorage.token, selectedCode.id);
			toast.success('删除成功');
			showDeleteConfirm = false;
			selectedCode = null;
			await loadCodes();
		} catch (error) {
			toast.error(`删除失败: ${error}`);
		}
	};

	// 创建成功后刷新
	const handleCreateSuccess = async () => {
		showCreateModal = false;
		await loadCodes();
	};

	// 编辑成功后刷新
	const handleEditSuccess = async () => {
		showEditModal = false;
		selectedCode = null;
		await loadCodes();
	};

	// 状态变化时重新加载
	$: if (statusFilter !== undefined) {
		currentPage = 0;
		loadCodes();
	}

	onMount(() => {
		loadCodes();
	});
</script>

<div class="flex flex-col h-full">
	<!-- 顶部操作栏 -->
	<div class="flex flex-wrap justify-between items-start gap-4 mb-4 pb-4 border-b dark:border-gray-700">
		<div class="flex-1 min-w-0">
			<h2 class="text-xl font-semibold text-gray-900 dark:text-white">兑换码管理</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
				创建和管理兑换码，用户可通过兑换码获得余额充值
			</p>
		</div>
		<button
			class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2 flex-shrink-0 whitespace-nowrap"
			on:click={() => (showCreateModal = true)}
		>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
			</svg>
			创建兑换码
		</button>
	</div>

	<!-- 筛选器 -->
	<div class="flex flex-wrap items-center gap-4 mb-4">
		<div class="flex items-center gap-2">
			<label class="text-sm font-medium text-gray-700 dark:text-gray-300 whitespace-nowrap">状态筛选:</label>
			<select
				bind:value={statusFilter}
				class="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-sm focus:ring-2 focus:ring-blue-500 min-w-[120px]"
			>
				<option value="all">全部</option>
				<option value="active">生效中</option>
				<option value="pending">未生效</option>
				<option value="expired">已过期</option>
				<option value="exhausted">已用尽</option>
				<option value="disabled">已禁用</option>
			</select>
		</div>

		<div class="text-sm text-gray-500 dark:text-gray-400">
			共 {total} 个兑换码
		</div>
	</div>

	<!-- 兑换码表格 -->
	<div class="flex-1 overflow-auto border border-gray-200 dark:border-gray-700 rounded-lg">
		{#if loading}
			<div class="flex items-center justify-center h-64">
				<Spinner className="size-8" />
			</div>
		{:else if codes.length === 0}
			<div class="flex flex-col items-center justify-center h-64 text-gray-400">
				<svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
				</svg>
				<p class="text-lg font-medium">暂无兑换码</p>
				<p class="text-sm mt-1">点击上方按钮创建第一个兑换码</p>
			</div>
		{:else}
			<table class="w-full">
				<thead class="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0">
					<tr>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">兑换码</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">金额</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">使用情况</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">有效期</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">状态</th>
						<th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">创建者</th>
						<th class="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">操作</th>
					</tr>
				</thead>
				<tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
					{#each codes as code (code.id)}
						<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
							<!-- 兑换码 -->
							<td class="px-4 py-3">
								<div class="flex items-center gap-2">
									<code class="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded font-mono text-sm">{code.code}</code>
									<button
										class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
										on:click={() => copyCode(code.code)}
									>
										<Tooltip content="复制">
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
											</svg>
										</Tooltip>
									</button>
								</div>
								{#if code.remark}
									<p class="text-xs text-gray-500 mt-1">{code.remark}</p>
								{/if}
							</td>

							<!-- 金额 -->
							<td class="px-4 py-3">
								<span class="text-sm font-medium">¥{code.amount.toFixed(2)}</span>
							</td>

							<!-- 使用情况 -->
							<td class="px-4 py-3">
								<div class="flex flex-col gap-1">
									<div class="text-sm">
										<span class="font-medium">{code.current_uses}</span> / {code.max_uses}
										<span class="text-gray-500 text-xs ml-1">({code.remaining_uses} 剩余)</span>
									</div>
									<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
										<div
											class="bg-blue-600 h-1.5 rounded-full transition-all"
											style="width: {(code.current_uses / code.max_uses) * 100}%"
										></div>
									</div>
								</div>
							</td>

							<!-- 有效期 -->
							<td class="px-4 py-3">
								<div class="text-xs">
									<div class="text-gray-500">开始: {dayjs.unix(code.start_time).format('YYYY-MM-DD HH:mm')}</div>
									<div class="text-gray-500">结束: {dayjs.unix(code.end_time).format('YYYY-MM-DD HH:mm')}</div>
								</div>
							</td>

							<!-- 状态 -->
							<td class="px-4 py-3">
								<span class="inline-flex px-2 py-1 text-xs font-medium rounded-full {getStatusColor(code.status)}">
									{formatStatus(code.status)}
								</span>
							</td>

							<!-- 创建者 -->
							<td class="px-4 py-3">
								<span class="text-sm text-gray-600 dark:text-gray-400">{code.creator_name}</span>
							</td>

							<!-- 操作 -->
							<td class="px-4 py-3">
								<div class="flex items-center justify-end gap-1 flex-shrink-0 min-w-fit">
									<Tooltip content="查看日志">
										<button
											class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors flex-shrink-0"
											on:click={() => { selectedCode = code; showLogsModal = true; }}
										>
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
											</svg>
										</button>
									</Tooltip>

									<Tooltip content="编辑">
										<button
											class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors flex-shrink-0"
											on:click={() => { selectedCode = code; showEditModal = true; }}
										>
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
											</svg>
										</button>
									</Tooltip>

									<Tooltip content={code.enabled ? '禁用' : '启用'}>
										<button
											class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors flex-shrink-0"
											on:click={() => handleToggle(code.id)}
										>
											{#if code.enabled}
												<svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
											{:else}
												<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
												</svg>
											{/if}
										</button>
									</Tooltip>

									<Tooltip content="删除">
										<button
											class="p-2 hover:bg-red-100 dark:hover:bg-red-900/20 rounded transition-colors text-red-600 flex-shrink-0"
											on:click={() => { selectedCode = code; showDeleteConfirm = true; }}
										>
											<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
												<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
											</svg>
										</button>
									</Tooltip>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
</div>

<!-- 创建模态框 -->
<CreateRedeemCodeModal bind:show={showCreateModal} onSuccess={handleCreateSuccess} />

<!-- 编辑模态框 -->
{#if selectedCode}
	<EditRedeemCodeModal bind:show={showEditModal} code={selectedCode} onSuccess={handleEditSuccess} />
{/if}

<!-- 日志模态框 -->
{#if selectedCode}
	<RedeemCodeLogsModal bind:show={showLogsModal} code={selectedCode} />
{/if}

<!-- 删除确认对话框 -->
<ConfirmDialog
	bind:show={showDeleteConfirm}
	title="确认删除"
	message="确定要删除此兑换码吗？删除后将无法恢复。"
	onConfirm={handleDelete}
/>

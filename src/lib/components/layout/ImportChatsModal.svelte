<script lang="ts">
	import { toast } from 'svelte-sonner';
import Modal from '../common/Modal.svelte';
import Spinner from '../common/Spinner.svelte';
import ArrowUpTray from '../icons/ArrowUpTray.svelte';
import ArchiveBox from '../icons/ArchiveBox.svelte';

	export let show = false;
	export let onImport: (chats: any[]) => Promise<void>;

	let dropActive = false;
	let loading = false;
	let importing = false;
	let filterOpen = true;
	let errorMsg = '';
	let successMsg = '';
	let fileName = '';
	
	// 对应 HTML 版本中的 rawData
	let rawChats: any[] = [];
	// 对应 HTML 版本中的 selectedIndices
	let selectedIndices: Set<number> = new Set();

	let fileInputEl: HTMLInputElement;

	// 重置状态
	const resetState = () => {
		errorMsg = '';
		successMsg = '';
		fileName = '';
		rawChats = [];
		selectedIndices = new Set();
		filterOpen = true;
		if (fileInputEl) fileInputEl.value = '';
	};

	$: if (!show) {
		resetState();
	}

	// 核心逻辑：读取并解析 JSON 数组
	const handleFiles = async (files: FileList | File[]) => {
		if (!files || files.length === 0) return;
		const file = files[0];
		
		loading = true;
		errorMsg = '';
		successMsg = '';
		fileName = file.name;
		rawChats = [];
		selectedIndices = new Set();

		try {
			const text = await file.text();
			let parsed: any;

			try {
				parsed = JSON.parse(text);
			} catch (e) {
				throw new Error('JSON 解析失败，请检查文件格式');
			}

			// 校验格式：必须是数组 [{}, {}]
			if (!Array.isArray(parsed)) {
				throw new Error('文件格式错误：JSON 根节点必须是数组 `[...]`');
			}

			if (parsed.length === 0) {
				throw new Error('JSON 数组为空');
			}

			rawChats = parsed;
			successMsg = `解析成功，共 ${rawChats.length} 条记录`;
			
			// 默认不全选，或者全选，取决于你的偏好。这里保持原有逻辑（不选或全选）
			// 这里改为：解析后默认显示列表，但不选中（等待用户操作），或者全选
			// 之前的 HTML 逻辑是空的，这里为了方便用户，可以默认不选，或者全选。
			// 让我们默认不选，让用户决定。
			selectedIndices = new Set(); 
			filterOpen = true;

		} catch (error) {
			console.error(error);
			errorMsg = error instanceof Error ? error.message : `${error}`;
			rawChats = [];
		} finally {
			loading = false;
		}
	};

	// 行选择切换
	const toggleRow = (idx: number) => {
		const next = new Set(selectedIndices);
		if (next.has(idx)) {
			next.delete(idx);
		} else {
			next.add(idx);
		}
		selectedIndices = next;
	};

	// 全选/取消全选
	const toggleSelectAll = (checked: boolean) => {
		selectedIndices = checked ? new Set(rawChats.map((_, idx) => idx)) : new Set();
	};

	// 导出并导入 (Export & Import)
	const confirmImport = async () => {
		if (!rawChats.length) {
			toast.error('请先上传文件');
			return;
		}

		if (selectedIndices.size === 0) {
			toast.error('未选择任何记录');
			return;
		}

		// 筛选数据
		const chatsToImport = rawChats.filter((_, idx) => selectedIndices.has(idx));

		try {
			importing = true;

			// 1. 生成并下载 JSON 文件 (对应 HTML 工具的导出功能)
			// 使用 null, 2 进行美化输出
			const jsonString = JSON.stringify(chatsToImport, null, 2); 
			const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `filtered_chats_${new Date().toISOString().slice(0, 10)}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);

			toast.success(`已导出 ${chatsToImport.length} 条记录`);

			// 2. 执行回调，将数据导入应用
			await onImport(chatsToImport);
			show = false;
			
		} catch (error) {
			console.error(error);
			toast.error(error instanceof Error ? error.message : `${error}`);
		} finally {
			importing = false;
		}
	};

	// 辅助显示函数 (对应 HTML 中的 renderTable)
	const formatDate = (value) => {
		if (!value) return '-';
		const dateObj = new Date(value);
		if (isNaN(dateObj.getTime())) return value;
		return dateObj.toLocaleString();
	};

	const displayRows = () =>
		rawChats.map((chat, idx) => {
			// 宽容处理字段
			const title = chat.title || '<无标题>';
			const dateRaw = chat.inserted_at || chat.created_at || chat.timestamp || chat.date || '-';
			const date = formatDate(dateRaw);
			return { idx, title, date };
		});

	const handleFileInputChange = (event: Event) => {
		const input = event.currentTarget as HTMLInputElement;
		handleFiles(input.files ?? []);
	};

	const handleSelectAllChange = (event: Event) => {
		const input = event.currentTarget as HTMLInputElement;
		toggleSelectAll(input.checked);
	};
</script>

<Modal bind:show size="xl" className="bg-white/95 dark:bg-gray-900/95 rounded-4xl p-1">
	<div class="p-6 space-y-6 font-primary">
		<div class="flex items-start justify-between gap-4">
			<div>
				<div class="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
					<span class="w-3 h-3 rounded bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></span>
					上传聊天记录
				</div>
				<div class="text-sm text-gray-500 dark:text-gray-400 mt-1">
					仅支持 JSON 格式，导入前请先选择或拖入文件
				</div>
			</div>
			<button
				class="text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
				on:click={() => (show = false)}
				aria-label="Close"
			>
				✕
			</button>
		</div>

		<div class="space-y-4">
			<div class="rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-3">
				<div class="flex items-center justify-between">
					<div class="text-sm font-semibold text-gray-800 dark:text-gray-100">上传聊天记录</div>
					{#if loading}
						<div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
							<Spinner className="size-4" />
							<span>正在解析...</span>
						</div>
					{/if}
				</div>

				<div
					class={`relative border-2 border-dashed rounded-xl p-6 transition flex flex-col items-center gap-3 text-center ${
						dropActive
							? 'border-blue-400 bg-blue-50/70 dark:border-blue-400/80 dark:bg-blue-950/40'
							: 'border-gray-200 dark:border-gray-800 bg-gray-50/40 dark:bg-gray-900'
					}`}
					on:dragover|preventDefault={() => (dropActive = true)}
					on:dragleave|preventDefault={() => (dropActive = false)}
					on:drop|preventDefault={(e) => {
						dropActive = false;
						handleFiles(e.dataTransfer?.files ?? []);
					}}
					role="button"
					tabindex="0"
				>
					<div class="w-12 h-12 rounded-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm flex items-center justify-center text-blue-500">
						<ArrowUpTray className="size-6" />
					</div>
					<div class="flex flex-col items-center gap-1 text-sm text-gray-700 dark:text-gray-200">
						<div class="font-medium text-gray-900 dark:text-white font-mono">
							{fileName ? `已选择：${fileName}` : '拖入 .json 文件'}
						</div>
						<div class="text-xs text-gray-500 dark:text-gray-400">仅支持 JSON 格式</div>
						<div class="flex items-center gap-2 mt-1">
							<button
								class="px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-850 text-gray-800 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 transition shadow-sm text-xs"
								on:click={() => fileInputEl.click()}
								type="button"
							>
								选择文件
							</button>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								格式要求: <code>[&#123;...&#125;, &#123;...&#125;]</code>
							</div>
						</div>
					</div>
					<input
						bind:this={fileInputEl}
						type="file"
						accept=".json,application/json"
						hidden
						on:change={handleFileInputChange}
					/>

					{#if errorMsg}
						<div class="w-full mt-2 text-xs text-red-500 bg-red-50/60 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2 text-left">
							{errorMsg}
						</div>
					{:else if successMsg}
						<div class="w-full mt-2 text-xs text-green-600 dark:text-green-400 bg-green-50/70 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-3 py-2 text-left">
							{successMsg}
						</div>
					{/if}

					{#if loading}
						<div class="absolute inset-0 bg-white/60 dark:bg-black/40 backdrop-blur-sm rounded-xl flex items-center justify-center">
							<Spinner className="size-6 text-blue-500" />
						</div>
					{/if}
				</div>
			</div>

			<div class="rounded-2xl border border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-3">
				<div class="flex items-center justify-between">
					<div class="text-sm font-semibold text-gray-800 dark:text-gray-100">
						2. 筛选记录
					</div>
					
					{#if rawChats.length > 0}
					<div class="flex items-center gap-3 text-xs text-gray-600 dark:text-gray-400">
						<span class="font-mono">总计: {rawChats.length} | 已选: {selectedIndices.size}</span>
						<label class="flex items-center gap-2 cursor-pointer select-none hover:text-gray-900 dark:hover:text-white transition-colors">
							<input
								type="checkbox"
								class="accent-blue-600 rounded"
								checked={rawChats.length > 0 && selectedIndices.size === rawChats.length}
								indeterminate={selectedIndices.size > 0 && selectedIndices.size < rawChats.length}
								on:change={handleSelectAllChange}
							/>
							<span>全选</span>
						</label>
					</div>
					{/if}
				</div>

				{#if filterOpen}
					<div class="max-h-64 overflow-auto rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/30 dark:bg-black/20">
						<table class="w-full text-sm border-collapse">
							<thead class="text-left bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400 sticky top-0 backdrop-blur-md">
								<tr>
									<th class="w-12 py-1.5 px-3 text-center">
										<input
											type="checkbox"
											class="accent-blue-600 rounded"
											checked={rawChats.length > 0 && selectedIndices.size === rawChats.length}
											indeterminate={selectedIndices.size > 0 && selectedIndices.size < rawChats.length}
											on:change={handleSelectAllChange}
										/>
									</th>
									<th class="py-1.5 px-3 font-medium text-xs uppercase tracking-wider w-full">标题</th>
									<th class="w-56 py-1.5 px-3 font-medium text-xs uppercase tracking-wider text-right">创建时间</th>
								</tr>
							</thead>
							<tbody>
								{#if !rawChats.length}
									<tr>
										<td colspan="3" class="py-10 text-center text-gray-500 dark:text-gray-500 text-xs">
											<div class="flex flex-col items-center gap-2 text-sm text-gray-500">
												<div class="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-400">
													<ArchiveBox className="size-5" />
												</div>
												<div>暂无数据，请先在上方上传文件</div>
											</div>
										</td>
									</tr>
								{:else}
									{#each displayRows() as row (row.idx)}
										<tr 
											class="border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors group"
										>
											<td class="py-2 px-3 text-center">
												<input
													type="checkbox"
													class="accent-blue-600 cursor-pointer"
													checked={selectedIndices.has(row.idx)}
													on:change={() => toggleRow(row.idx)}
												/>
											</td>
											<td class="py-2 px-3">
												<div class="text-gray-900 dark:text-gray-200 font-medium truncate max-w-[300px]" title={row.title}>
													{row.title}
												</div>
											</td>
											<td class="py-2 px-3 text-xs font-mono text-blue-600 dark:text-blue-400 text-right">
												{row.date}
											</td>
										</tr>
									{/each}
								{/if}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<div class="flex items-center justify-end gap-3 pt-2">
				<button
					class="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition underline-offset-2 hover:underline"
					on:click={() => (show = false)}
					type="button"
				>
					取消
				</button>
				<button
					class="px-4 py-2 text-sm rounded-xl bg-green-600 text-white hover:bg-green-700 hover:shadow-[0_0_12px_rgba(22,163,74,0.4)] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none flex items-center gap-2 transition-all font-medium"
					on:click={confirmImport}
					disabled={loading || importing || selectedIndices.size === 0}
					type="button"
				>
					{#if importing}
						<Spinner className="size-4" />
					{/if}
					<span>导入 ({selectedIndices.size})</span>
				</button>
			</div>
		</div>
	</div>
</Modal>

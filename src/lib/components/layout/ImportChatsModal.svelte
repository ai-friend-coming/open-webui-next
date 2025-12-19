<script lang="ts">
    import { toast } from 'svelte-sonner';
    import { slide, fly } from 'svelte/transition';
    import Modal from '../common/Modal.svelte';
    import Spinner from '../common/Spinner.svelte';
    import ArrowUpTray from '../icons/ArrowUpTray.svelte';
    import ArchiveBox from '../icons/ArchiveBox.svelte';
    import DocumentText from '../icons/DocumentText.svelte';
    import MagnifyingGlass from '../icons/MagnifyingGlass.svelte';

    export let show = false;
    export let onImport: (chats: any[]) => Promise<void>;

    let dropActive = false;
    let loading = false;
    let importing = false;
    let errorMsg = '';
    let rawChats: any[] = [];
    let selectedIndices: Set<number> = new Set();
    let fileInputEl: HTMLInputElement;
    let fileName = '';
    let searchQuery = '';

    // 重置状态
    const resetState = () => {
        errorMsg = '';
        fileName = '';
        rawChats = [];
        selectedIndices = new Set();
        searchQuery = '';
        if (fileInputEl) fileInputEl.value = '';
    };

    $: if (!show) {
        resetState();
    }

    // 处理文件
    const handleFiles = async (files: FileList | File[]) => {
        if (!files || files.length === 0) return;
        const file = files[0];
        
        loading = true;
        errorMsg = '';
        fileName = file.name;
        
        try {
            const text = await file.text();
            let parsed: any;
            try {
                parsed = JSON.parse(text);
            } catch (e) {
                throw new Error('无法解析 JSON，请检查文件格式');
            }

            if (!Array.isArray(parsed)) throw new Error('JSON 格式错误：根节点必须是数组');
            if (parsed.length === 0) throw new Error('JSON 数组为空');

            rawChats = parsed;
            selectedIndices = new Set(); 
            toast.success(`解析成功，共 ${rawChats.length} 条记录`);
        } catch (error) {
            console.error(error);
            errorMsg = error instanceof Error ? error.message : `${error}`;
            rawChats = [];
            fileName = '';
        } finally {
            loading = false;
        }
    };

    // 切换选择
    const toggleRow = (idx: number) => {
        const next = new Set(selectedIndices);
        if (next.has(idx)) next.delete(idx);
        else next.add(idx);
        selectedIndices = next;
    };

    // 过滤显示的行 (支持搜索)
    $: filteredChats = rawChats.map((chat, originalIdx) => ({...chat, originalIdx})).filter(item => {
        if (!searchQuery) return true;
        return (item.title || '').toLowerCase().includes(searchQuery.toLowerCase());
    });

    // 全选/反选 (仅针对当前搜索结果)
    const toggleSelectAll = (checked: boolean) => {
        const next = new Set(selectedIndices);
        filteredChats.forEach(item => {
            if (checked) next.add(item.originalIdx);
            else next.delete(item.originalIdx);
        });
        selectedIndices = next;
    };

    // 检查是否全选 (针对当前搜索结果)
    $: isAllSelected = filteredChats.length > 0 && filteredChats.every(item => selectedIndices.has(item.originalIdx));
    $: isIndeterminate = filteredChats.some(item => selectedIndices.has(item.originalIdx)) && !isAllSelected;

    // 导入逻辑
    const confirmImport = async () => {
        if (!selectedIndices.size) return toast.error('未选择任何记录');
        
        const chatsToImport = rawChats.filter((_, idx) => selectedIndices.has(idx));

        try {
            importing = true;
            await onImport(chatsToImport);
            show = false;
            toast.success(`成功导入 ${chatsToImport.length} 条对话`);
        } catch (error) {
            toast.error(String(error));
        } finally {
            importing = false;
        }
    };
</script>

<Modal bind:show size="xl" className="bg-white/95 dark:bg-gray-900/95 backdrop-blur-md rounded-3xl overflow-hidden">
    <div class="flex flex-col h-[80vh] max-h-[700px] font-primary">
        
        <div class="px-6 py-5 border-b border-gray-100 dark:border-gray-800 flex justify-between items-center bg-white dark:bg-gray-900">
            <div>
                <h2 class="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <span class="text-blue-500"><ArrowUpTray className="size-5 stroke-2"/></span>
                    导入聊天记录
                </h2>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">支持 WebUI JSON 格式导出文件</p>
            </div>
            <button class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors" on:click={() => show = false}>
                <span class="text-xl leading-none">&times;</span>
            </button>
        </div>

        <div class="flex-1 overflow-hidden flex flex-col p-6 gap-5 bg-gray-50/50 dark:bg-black/20">
            
            {#if rawChats.length === 0}
                <div 
                    class="flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-10 transition-all duration-200
                    {dropActive ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-700 hover:border-blue-400 hover:bg-white dark:hover:bg-gray-800/50'}"
                    on:dragover|preventDefault={() => dropActive = true}
                    on:dragleave|preventDefault={() => dropActive = false}
                    on:drop|preventDefault={(e) => { dropActive = false; handleFiles(e.dataTransfer?.files ?? []); }}
                    role="button"
                    tabindex="0"
                >
                    {#if loading}
                        <Spinner className="size-10 text-blue-500" />
                        <div class="mt-4 text-sm text-gray-500">正在解析文件...</div>
                    {:else}
                        <div class="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 text-blue-600 rounded-full flex items-center justify-center mb-4 shadow-sm">
                            <DocumentText className="size-8" />
                        </div>
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white">点击或拖拽 JSON 文件至此</h3>
                        <p class="text-sm text-gray-500 mt-2 mb-6 max-w-xs text-center">只能上传符合格式的 JSON 数组文件</p>
                        <button 
                            class="px-6 py-2.5 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-xl font-medium shadow-lg hover:shadow-xl transition-transform active:scale-95"
                            on:click={(e) => { e.stopPropagation(); fileInputEl.click(); }}
                        >
                            选择文件
                        </button>
                    {/if}
                    
                    {#if errorMsg}
                        <div class="mt-6 px-4 py-2 bg-red-50 text-red-600 text-xs rounded-lg border border-red-100">
                            {errorMsg}
                        </div>
                    {/if}
                </div>
            {:else}
                <div class="flex items-center justify-between bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm shrink-0" transition:slide>
                    <div class="flex items-center gap-3 overflow-hidden">
                        <div class="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 text-green-600 flex items-center justify-center shrink-0">
                            <DocumentText className="size-6" />
                        </div>
                        <div class="min-w-0">
                            <div class="font-medium text-gray-900 dark:text-white truncate" title={fileName}>{fileName}</div>
                            <div class="text-xs text-gray-500">包含 {rawChats.length} 条记录</div>
                        </div>
                    </div>
                    <button 
                        class="text-xs text-blue-600 hover:text-blue-700 hover:underline px-2"
                        on:click={resetState}
                    >
                        重新上传
                    </button>
                </div>

                <div class="flex-1 flex flex-col bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden" transition:fly={{y: 20}}>
                    
                    <div class="p-3 border-b border-gray-100 dark:border-gray-800 flex flex-wrap gap-3 items-center justify-between">
                        <div class="flex items-center gap-3 pl-1">
                            <input 
                                type="checkbox" 
                                class="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 transition cursor-pointer"
                                checked={isAllSelected}
                                indeterminate={isIndeterminate}
                                on:change={(e) => toggleSelectAll(e.currentTarget.checked)}
                            />
                            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
                                {selectedIndices.size > 0 ? `已选 ${selectedIndices.size} 项` : '选择记录'}
                            </span>
                        </div>
                        
                        <div class="relative w-full sm:w-64">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                <MagnifyingGlass className="size-4" />
                            </div>
                            <input 
                                type="text"
                                bind:value={searchQuery}
                                placeholder="搜索标题..."
                                class="w-full pl-9 pr-4 py-1.5 text-sm bg-gray-50 dark:bg-gray-800 border-none rounded-lg focus:ring-2 focus:ring-blue-500/50 text-gray-900 dark:text-white"
                            />
                        </div>
                    </div>

                    <div class="flex-1 overflow-y-auto min-h-0">
                        {#if filteredChats.length === 0}
                            <div class="h-full flex flex-col items-center justify-center text-gray-400">
                                <ArchiveBox className="size-8 opacity-50 mb-2" />
                                <span class="text-sm">没有找到匹配的记录</span>
                            </div>
                        {:else}
                            <div class="divide-y divide-gray-100 dark:divide-gray-800">
                                {#each filteredChats as item (item.originalIdx)}
                                    <div 
                                        class="flex items-center gap-4 px-4 py-3 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 cursor-pointer transition-colors group {selectedIndices.has(item.originalIdx) ? 'bg-blue-50/80 dark:bg-blue-900/20' : ''}"
                                        on:click={() => toggleRow(item.originalIdx)}
                                        role="button"
                                        tabindex="0"
                                    >
                                        <div class="shrink-0 flex items-center">
                                            <input 
                                                type="checkbox" 
                                                class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-offset-0 cursor-pointer pointer-events-none"
                                                checked={selectedIndices.has(item.originalIdx)}
                                            />
                                        </div>
                                        
                                        <div class="flex-1 min-w-0">
                                            <div class="flex items-center justify-between gap-2">
                                                <div class="font-medium text-gray-900 dark:text-gray-100 truncate text-sm">
                                                    {item.title || '无标题对话'}
                                                </div>
                                                {#if item.messages}
                                                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500 shrink-0">
                                                        {item.messages.length} msg
                                                    </span>
                                                {/if}
                                            </div>
                                            
                                            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 flex gap-2">
                                                <span>#{item.originalIdx + 1}</span>
                                            </div>
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        {/if}
                    </div>
                    
                    <div class="px-4 py-2 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 text-xs text-gray-500 flex justify-between">
                        <span>显示 {filteredChats.length} 条</span>
                        {#if selectedIndices.size > 0}
                            <span class="text-blue-600 dark:text-blue-400">准备导入 {selectedIndices.size} 条</span>
                        {/if}
                    </div>
                </div>
            {/if}
        </div>

        <div class="px-6 py-4 border-t border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 flex justify-end gap-3 shrink-0">
            <button 
                class="px-5 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition font-medium"
                on:click={() => show = false}
            >
                取消
            </button>
            <button 
                class="px-6 py-2 text-sm text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-lg shadow-blue-600/20 disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed transition-all font-medium flex items-center gap-2"
                on:click={confirmImport}
                disabled={loading || importing || selectedIndices.size === 0}
            >
                {#if importing}
                    <Spinner className="size-4" />
                {/if}
                确认导入 ({selectedIndices.size})
            </button>
        </div>
    </div>
    
    <input 
        bind:this={fileInputEl}
        type="file" 
        accept=".json"
        class="hidden"
        on:change={(e) => handleFiles(e.currentTarget.files ?? [])}
    />
</Modal>
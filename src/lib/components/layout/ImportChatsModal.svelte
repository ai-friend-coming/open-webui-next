<script lang="ts">
    import { toast } from 'svelte-sonner';
    import { slide, fly } from 'svelte/transition';
    import Modal from '../common/Modal.svelte';
    import Spinner from '../common/Spinner.svelte';
    import ArrowUpTray from '../icons/ArrowUpTray.svelte';
    import ArchiveBox from '../icons/ArchiveBox.svelte';
    import DocumentText from '../icons/DocumentText.svelte';
    import MagnifyingGlass from '../icons/MagnifyingGlass.svelte';
    import { trackImportChatsFileParsed, trackImportChatsModalClosed } from '$lib/posthog';

    export let show = false;
    export let onImport: (chats: any[]) => Promise<void>;

    let dropActive = false;
    let loading = false;
    let importing = false;
    let errorMsg = '';
    let rawChats: any[] = [];

    // 聊天配置接口
    interface ChatConfig {
        selected: boolean;
        importMemory: boolean;
    }

    // 使用 Map 存储每个聊天的配置
    let chatConfigs: Map<number, ChatConfig> = new Map();

    // 计算属性：保持向后兼容
    $: selectedIndices = new Set(
        Array.from(chatConfigs.entries())
            .filter(([_, config]) => config.selected)
            .map(([idx, _]) => idx)
    );

    // 主控开关状态
    $: {
        const selectedConfigs = Array.from(chatConfigs.entries())
            .filter(([_, config]) => config.selected)
            .map(([_, config]) => config);

        if (selectedConfigs.length === 0) {
            allMemoryEnabled = false;
            allMemoryIndeterminate = false;
        } else {
            const enabledCount = selectedConfigs.filter(c => c.importMemory).length;
            allMemoryEnabled = enabledCount === selectedConfigs.length;
            allMemoryIndeterminate = enabledCount > 0 && enabledCount < selectedConfigs.length;
        }
    }

    let allMemoryEnabled = false;
    let allMemoryIndeterminate = false;

    let fileInputEl: HTMLInputElement;
    let fileName = '';
    let searchQuery = '';
    let showExportGuide = false;
    let importCompleted = false;  // 标记是否完成导入（用于埋点4判断）

    // 重置状态
    const resetState = () => {
        errorMsg = '';
        fileName = '';
        rawChats = [];
        chatConfigs = new Map();
        searchQuery = '';
        showExportGuide = false;
        if (fileInputEl) fileInputEl.value = '';
    };

    $: if (!show) {
        // 埋点4：用户中途关闭 Modal（未完成导入）
        if (!importCompleted) {
            const stage = rawChats.length > 0 ? 'after_upload' : 'before_upload';
            trackImportChatsModalClosed(stage);
        }
        importCompleted = false;  // 重置状态
        resetState();
    }

    // 提取聊天记录的时间戳（兼容多种格式）
    const extractTimestamp = (chat: any): number => {
        // 尝试获取各种时间戳字段
        const timestamp =
            chat?.timestamp ||
            chat?.updated_at ||
            chat?.created_at ||
            chat?.create_time ||
            chat?.chat?.timestamp ||
            chat?.chat?.updated_at ||
            chat?.chat?.created_at;

        if (!timestamp) return 0;

        // 处理不同格式的时间戳
        if (typeof timestamp === 'number') {
            // 如果是毫秒级时间戳（13位），转换为秒级
            return timestamp > 10000000000 ? Math.floor(timestamp / 1000) : timestamp;
        }

        if (typeof timestamp === 'string') {
            // 尝试解析ISO字符串或其他格式
            const date = new Date(timestamp);
            return isNaN(date.getTime()) ? 0 : Math.floor(date.getTime() / 1000);
        }

        return 0;
    };

    // 解析 Chatbox 格式的 txt 文件
    const parseChatboxFormat = (text: string): any => {
        const lines = text.split('\n');
        const titleMatch = text.match(/====+\s*\[\[(.+?)\]\]\s*====+/);
        const title = titleMatch ? titleMatch[1].trim() : 'Imported Chat';

        const messages: any[] = [];
        let currentRole = '';
        let currentContent: string[] = [];

        for (const line of lines) {
            // 检测角色标记
            const roleMatch = line.match(/^▶\s*(SYSTEM|USER|ASSISTANT):\s*$/);
            if (roleMatch) {
                // 保存上一条消息
                if (currentRole && currentContent.length > 0) {
                    messages.push({
                        role: currentRole.toLowerCase(),
                        content: currentContent.join('\n').trim()
                    });
                }
                // 开始新消息
                currentRole = roleMatch[1];
                currentContent = [];
            } else if (currentRole && line.trim() &&
                       !line.includes('====') &&
                       !line.includes('----') &&
                       !line.includes('Chatbox AI')) {
                // 累积消息内容
                currentContent.push(line);
            }
        }

        // 保存最后一条消息
        if (currentRole && currentContent.length > 0) {
            messages.push({
                role: currentRole.toLowerCase(),
                content: currentContent.join('\n').trim()
            });
        }

        const now = Math.floor(Date.now() / 1000);
        return {
            title,
            chat: {
                messages,
                models: ["chatbox"]
            },
            timestamp: now,
            created_at: now,
            updated_at: now
        };
    };

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

            // 检测文件类型
            if (file.name.endsWith('.txt')) {
                // Chatbox 格式
                try {
                    parsed = [parseChatboxFormat(text)];
                } catch (e) {
                    throw new Error('无法解析 Chatbox 格式，请检查文件内容');
                }
            } else {
                // JSON 格式
                try {
                    parsed = JSON.parse(text);
                } catch (e) {
                    throw new Error('无法解析 JSON，请检查文件格式');
                }
            }

            // Handle Grok format (object with conversations array)
            if (parsed && typeof parsed === 'object' && Array.isArray(parsed.conversations)) {
                parsed = parsed.conversations;
            }
            // Handle AI Studio single conversation (object with chunkedPrompt)
            else if (parsed && typeof parsed === 'object' && 'chunkedPrompt' in parsed) {
                parsed = [parsed];
            }

            if (!Array.isArray(parsed)) throw new Error('JSON 格式错误');
            if (parsed.length === 0) throw new Error('未检测到聊天记录');

            // 按时间戳从新到旧排序
            rawChats = parsed.sort((a, b) => {
                const timeA = extractTimestamp(a);
                const timeB = extractTimestamp(b);
                return timeB - timeA; // 降序：新的在前
            });

            chatConfigs = new Map();
            // 埋点2：文件解析成功
            trackImportChatsFileParsed(rawChats.length);
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

    // 最大导入数量限制
    const MAX_IMPORT_CHATS = 50;

    // 切换单个聊天的记忆导入开关
    const toggleMemory = (idx: number, event: Event) => {
        event.stopPropagation();

        const config = chatConfigs.get(idx);
        if (config) {
            config.importMemory = !config.importMemory;
            chatConfigs = chatConfigs; // 触发响应式更新
        }
    };

    // 切换所有已选中聊天的记忆开关
    const toggleAllMemory = (enabled: boolean) => {
        for (const [idx, config] of chatConfigs.entries()) {
            if (config.selected) {
                config.importMemory = enabled;
            }
        }
        chatConfigs = chatConfigs;
    };

    // 切换选择
    const toggleRow = (idx: number) => {
        const config = chatConfigs.get(idx);

        if (config?.selected) {
            // 取消选中：移除配置
            chatConfigs.delete(idx);
        } else {
            // 选中：检查数量限制
            const selectedCount = Array.from(chatConfigs.values())
                .filter(c => c.selected).length;

            if (selectedCount >= MAX_IMPORT_CHATS) {
                toast.error(`最多只能选择 ${MAX_IMPORT_CHATS} 个对话`);
                return;
            }

            // 添加配置（默认开启记忆导入）
            chatConfigs.set(idx, {
                selected: true,
                importMemory: true
            });
        }

        chatConfigs = chatConfigs; // 触发响应式更新
    };

    // 过滤显示的行 (支持搜索)
    $: filteredChats = rawChats.map((chat, originalIdx) => ({...chat, originalIdx})).filter(item => {
        if (!searchQuery) return true;
        return (item.title || '').toLowerCase().includes(searchQuery.toLowerCase());
    });

    // 全选/反选 (仅针对当前搜索结果)
    const toggleSelectAll = (checked: boolean) => {
        if (checked) {
            // 全选：检查数量限制
            const currentSelected = Array.from(chatConfigs.values())
                .filter(c => c.selected).length;
            const toAdd = filteredChats.filter(item =>
                !chatConfigs.get(item.originalIdx)?.selected
            );

            if (currentSelected + toAdd.length > MAX_IMPORT_CHATS) {
                toast.error(`最多只能选择 ${MAX_IMPORT_CHATS} 个对话，当前已选 ${currentSelected} 个`);
                return;
            }

            toAdd.forEach(item => {
                chatConfigs.set(item.originalIdx, {
                    selected: true,
                    importMemory: true // 默认开启
                });
            });
        } else {
            // 反选：仅移除当前搜索结果中的项
            filteredChats.forEach(item => {
                chatConfigs.delete(item.originalIdx);
            });
        }

        chatConfigs = chatConfigs;
    };

    // 检查是否全选 (针对当前搜索结果)
    $: isAllSelected = filteredChats.length > 0 && filteredChats.every(item => selectedIndices.has(item.originalIdx));
    $: isIndeterminate = filteredChats.some(item => selectedIndices.has(item.originalIdx)) && !isAllSelected;

    // 导入逻辑
    const confirmImport = async () => {
        if (!selectedIndices.size) return toast.error('未选择任何记录');

        // 最终验证数量限制
        if (selectedIndices.size > MAX_IMPORT_CHATS) {
            return toast.error(`最多只能导入 ${MAX_IMPORT_CHATS} 个对话，当前选择了 ${selectedIndices.size} 个`);
        }

        // 构建导入数据（包含记忆开关信息）
        const chatsToImport = rawChats
            .map((chat, idx) => {
                const config = chatConfigs.get(idx);
                if (!config?.selected) return null;

                return {
                    chat,
                    importMemory: config.importMemory
                };
            })
            .filter(item => item !== null);

        try {
            importing = true;
            await onImport(chatsToImport);
            importCompleted = true;  // 标记导入成功，避免触发埋点4
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
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">支持 WebUI、DeepSeek、ChatGPT、Gemini、Grok JSON 格式</p>
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
                        <h3 class="text-lg font-medium text-gray-900 dark:text-white">点击或拖拽文件至此</h3>
                        <p class="text-sm text-gray-500 mt-2 mb-6 max-w-xs text-center">支持 JSON 或 Chatbox TXT 格式</p>
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

                <!-- 导出指南 -->
                <div class="bg-blue-50/50 dark:bg-blue-900/10 rounded-lg border border-blue-200 dark:border-blue-800/30 overflow-hidden">
                    <button
                        class="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-blue-100/50 dark:hover:bg-blue-900/20 transition-colors"
                        on:click={() => showExportGuide = !showExportGuide}
                    >
                        <span class="text-xs font-medium text-blue-700 dark:text-blue-300">💡 如何导出聊天记录?</span>
                        <span class="text-blue-400 text-xs transform transition-transform {showExportGuide ? 'rotate-180' : ''}">▼</span>
                    </button>

                    {#if showExportGuide}
                        <div class="px-3 pb-2 space-y-1.5 text-xs" transition:slide>
                            <div class="flex items-center gap-2 py-1.5">
                                <span class="shrink-0 w-4">🌊</span>
                                <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">DeepSeek</span>
                                <span class="text-gray-600 dark:text-gray-400 truncate">设置 → 数据 → 导出</span>
                            </div>

                            <div class="flex items-center gap-2 py-1.5">
                                <span class="shrink-0 w-4">💬</span>
                                <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">ChatGPT</span>
                                <span class="text-gray-600 dark:text-gray-400 truncate">设置 → 数据控制 → 导出数据 → 提取 conversations.json</span>
                            </div>

                            <div class="flex items-center gap-2 py-1.5">
                                <span class="shrink-0 w-4">✨</span>
                                <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">Gemini</span>
                                <span class="text-gray-600 dark:text-gray-400 truncate">Google Takeout → 勾选 Gemini Apps</span>
                            </div>

                            <div class="flex flex-col gap-1 py-1.5">
                                <div class="flex items-center gap-2">
                                    <span class="shrink-0 w-4">𝕏</span>
                                    <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">Grok</span>
                                    <span class="text-gray-600 dark:text-gray-400 truncate">X 设置 → 您的账户 → 下载数据归档</span>
                                </div>
                                <div class="pl-6 text-[11px] text-gray-500 dark:text-gray-500">
                                    📦 解压后上传 <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-blue-600 dark:text-blue-400">prod-grok-backend.json</code> 文件
                                </div>
                            </div>

                            <div class="flex flex-col gap-1 py-1.5">
                                <div class="flex items-center gap-2">
                                    <span class="shrink-0 w-4">🧪</span>
                                    <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">AI Studio</span>
                                    <span class="text-gray-600 dark:text-gray-400 truncate">Google Drive → 📁 Google AI Studio 文件夹</span>
                                </div>
                                <div class="pl-6 text-[11px] text-gray-500 dark:text-gray-500">
                                    📥 下载对应标题文件 (无后缀，内容即 JSON)
                                </div>
                            </div>

                            <div class="flex flex-col gap-1 py-1.5">
                                <div class="flex items-center gap-2">
                                    <span class="shrink-0 w-4">📦</span>
                                    <span class="font-medium text-gray-900 dark:text-white w-16 shrink-0">Chatbox</span>
                                    <span class="text-gray-600 dark:text-gray-400 truncate">右键聊天 → 导出为 Markdown</span>
                                </div>
                                <div class="pl-6 text-[11px] text-gray-500 dark:text-gray-500">
                                    📄 上传导出的 <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-blue-600 dark:text-blue-400">.txt</code> 文件
                                </div>
                            </div>
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
                            <div class="sensitive font-medium text-gray-900 dark:text-white truncate" title={fileName}>{fileName}</div>
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
                        <div class="flex items-center gap-3 pl-1 flex-1">
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

                            <!-- 主控记忆开关 -->
                            {#if selectedIndices.size > 0}
                                <div class="flex items-center gap-2 ml-4 pl-4 border-l border-gray-200 dark:border-gray-700">
                                    <span class="text-xs text-gray-600 dark:text-gray-400">导入记忆</span>
                                    <input
                                        type="checkbox"
                                        class="w-4 h-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                                        checked={allMemoryEnabled}
                                        indeterminate={allMemoryIndeterminate}
                                        on:change={(e) => toggleAllMemory(e.currentTarget.checked)}
                                        on:click={(e) => e.stopPropagation()}
                                    />
                                </div>
                            {/if}
                        </div>
                        
                        <div class="relative w-full sm:w-64">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                <MagnifyingGlass className="size-4" />
                            </div>
                            <div class='sensitive'>
                                <input 
                                    type="text"
                                    bind:value={searchQuery}
                                    placeholder="搜索标题..."
                                    class="w-full pl-9 pr-4 py-1.5 text-sm bg-gray-50 dark:bg-gray-800 border-none rounded-lg focus:ring-2 focus:ring-blue-500/50 text-gray-900 dark:text-white"
                                />
                            </div>
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
                                                <div class="sensitive font-medium text-gray-900 dark:text-gray-100 truncate text-sm">
                                                    {item.title || '无标题对话'}
                                                </div>

                                                <div class="flex items-center gap-2 shrink-0">
                                                    {#if item.messages}
                                                        <span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-500">
                                                            {item.messages.length} msg
                                                        </span>
                                                    {/if}

                                                    <!-- 记忆导入开关 -->
                                                    {#if chatConfigs.get(item.originalIdx)?.selected}
                                                        <div
                                                            class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800"
                                                            on:click={(e) => e.stopPropagation()}
                                                        >
                                                            <span class="text-[10px] font-medium text-emerald-700 dark:text-emerald-400">
                                                                记忆
                                                            </span>
                                                            <input
                                                                type="checkbox"
                                                                class="w-3 h-3 rounded border-emerald-300 text-emerald-600 focus:ring-emerald-500 cursor-pointer"
                                                                checked={chatConfigs.get(item.originalIdx)?.importMemory ?? true}
                                                                on:change={(e) => toggleMemory(item.originalIdx, e)}
                                                            />
                                                        </div>
                                                    {/if}
                                                </div>
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
                            {@const memoryCount = Array.from(chatConfigs.values())
                                .filter(c => c.selected && c.importMemory).length}
                            <span class="text-blue-600 dark:text-blue-400">
                                准备导入 {selectedIndices.size} 条
                                {#if memoryCount > 0}
                                    <span class="text-emerald-600 dark:text-emerald-400">
                                        (含记忆 {memoryCount})
                                    </span>
                                {/if}
                            </span>
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
        accept=".json,.txt"
        class="hidden"
        on:change={(e) => handleFiles(e.currentTarget.files ?? [])}
    />
</Modal>
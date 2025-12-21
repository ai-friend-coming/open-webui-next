<script lang="ts">
	import { getContext, tick, onDestroy } from 'svelte';
	import { goto, afterNavigate } from '$app/navigation';
	import { fly, fade } from 'svelte/transition';

	import {
		chats,
		pinnedChats,
		showMobileChatDrawer,
		showImportChatsModal,
		scrollPaginationEnabled,
		currentChatPage,
		tags,
		showSearch
	} from '$lib/stores';

	import { getChatList, getAllTags, getPinnedChatList } from '$lib/apis/chats';

	import ChatItem from '$lib/components/layout/Sidebar/ChatItem.svelte';
	import Folder from '$lib/components/common/Folder.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Loader from '$lib/components/common/Loader.svelte';
	import PencilSquare from '$lib/components/icons/PencilSquare.svelte';
	import Search from '$lib/components/icons/Search.svelte';

	const i18n = getContext('i18n');

	// Drawer state
	let drawerElement: HTMLElement | null = null;
	let isDragging = false;
	let startY = 0;
	let startHeight = 0;
	let currentHeight = 60; // percentage of viewport height
	const minHeight = 60;
	const maxHeight = 95;
	const closeThreshold = 30; // percentage below which drawer closes

	// Chat state
	let shiftKey = false;
	let selectedChatId: string | null = null;
	let showPinnedChat = true;
	let chatListLoading = false;
	let allChatsLoaded = false;
	let initChatListLoading = false;

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			closeDrawer();
		}
	};

	const closeDrawer = async () => {
		currentHeight = minHeight;
		await tick();
		showMobileChatDrawer.set(false);
	};

	// Touch/Mouse handlers for dragging
	const handleDragStart = (e: TouchEvent | MouseEvent) => {
		isDragging = true;
		startY = 'touches' in e ? e.touches[0].clientY : e.clientY;
		startHeight = currentHeight;
		document.body.style.overflow = 'hidden';
		document.body.style.userSelect = 'none';
	};

	const handleDragMove = (e: TouchEvent | MouseEvent) => {
		if (!isDragging) return;

		const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
		const deltaY = startY - clientY;
		const deltaPercent = (deltaY / window.innerHeight) * 100;

		let newHeight = startHeight + deltaPercent;
		newHeight = Math.max(10, Math.min(maxHeight, newHeight));
		currentHeight = newHeight;
	};

	const handleDragEnd = () => {
		if (!isDragging) return;
		isDragging = false;
		document.body.style.overflow = '';
		document.body.style.userSelect = '';

		// Snap to positions or close
		if (currentHeight < closeThreshold) {
			closeDrawer();
		} else if (currentHeight < (minHeight + maxHeight) / 2) {
			currentHeight = minHeight;
		} else {
			currentHeight = maxHeight;
		}
	};

	// Chat list functions
	const initChatList = async () => {
		if (initChatListLoading) return;
		initChatListLoading = true;

		try {
			currentChatPage.set(1);
			allChatsLoaded = false;

			await Promise.all([
				(async () => {
					try {
						const _tags = await getAllTags(localStorage.token);
						tags.set(_tags);
					} catch (err) {
						tags.set([]);
					}
				})(),
				(async () => {
					try {
						const _pinnedChats = await getPinnedChatList(localStorage.token);
						pinnedChats.set(_pinnedChats);
					} catch (err) {
						pinnedChats.set([]);
					}
				})(),
				(async () => {
					try {
						const _chats = await getChatList(localStorage.token, $currentChatPage);
						await chats.set(_chats);
					} catch (err) {
						await chats.set([]);
					}
				})()
			]);

			scrollPaginationEnabled.set(true);
		} finally {
			initChatListLoading = false;
		}
	};

	const loadMoreChats = async () => {
		if (chatListLoading || allChatsLoaded) return;
		chatListLoading = true;

		try {
			currentChatPage.set($currentChatPage + 1);
			const newChatList = await getChatList(localStorage.token, $currentChatPage).catch(() => []);
			allChatsLoaded = newChatList.length === 0;

			if (newChatList.length > 0) {
				await chats.set([...($chats ? $chats : []), ...newChatList]);
			}
		} finally {
			chatListLoading = false;
		}
	};

	const handleNewChat = async () => {
		await closeDrawer();
		goto('/');
	};

	const handleImport = async () => {
		await closeDrawer();
		showImportChatsModal.set(true);
	};

	// 导航完成后自动关闭抽屉
	afterNavigate(() => {
		if ($showMobileChatDrawer) {
			closeDrawer();
		}
	});

	const tagEventHandler = async (type: string, tagName: string, chatId: string) => {
		if (type === 'delete' || type === 'add') {
			initChatList();
		}
	};

	$: if ($showMobileChatDrawer) {
		currentHeight = minHeight;
		initChatList();
		window.addEventListener('keydown', handleKeyDown);
		document.body.style.overflow = 'hidden';
	} else {
		window.removeEventListener('keydown', handleKeyDown);
		document.body.style.overflow = '';
	}

	onDestroy(() => {
		window.removeEventListener('keydown', handleKeyDown);
		document.body.style.overflow = '';
	});
</script>

<svelte:window
	on:mousemove={handleDragMove}
	on:mouseup={handleDragEnd}
	on:touchmove={handleDragMove}
	on:touchend={handleDragEnd}
/>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->

{#if $showMobileChatDrawer}
	<div
		class="fixed inset-0 bg-black/60 z-999"
		transition:fade={{ duration: 200 }}
		on:mousedown={closeDrawer}
	/>

	<div
		bind:this={drawerElement}
		class="fixed left-0 right-0 bottom-0 bg-gray-50 dark:bg-gray-900 rounded-t-2xl z-999 flex flex-col"
		style="top: max({100 - currentHeight}vh, env(safe-area-inset-top, 0px)); transition: {isDragging ? 'none' : 'top 0.3s ease-out'};"
		transition:fly={{ y: 300, duration: 300 }}
		on:mousedown={(e) => e.stopPropagation()}
	>
		<!-- Drag Handle -->
		<div
			class="flex-shrink-0 pt-3 pb-2 cursor-grab active:cursor-grabbing touch-none"
			on:mousedown={handleDragStart}
			on:touchstart={handleDragStart}
		>
			<div class="w-10 h-1 bg-gray-300 dark:bg-gray-600 rounded-full mx-auto" />
		</div>

		<!-- Header -->
		<div class="flex-shrink-0 flex items-center justify-between px-4 pb-3 border-b border-gray-100 dark:border-gray-800">
			<h2 class="text-lg font-semibold text-gray-900 dark:text-white">{$i18n.t('Chats')}</h2>
		</div>

		<!-- Quick Actions -->
		<div class="flex-shrink-0 flex items-center gap-2 px-4 py-3 border-b border-gray-100 dark:border-gray-800">
			<button
				class="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-gray-900 dark:bg-white text-white dark:text-gray-900 font-medium text-sm"
				on:click={handleNewChat}
			>
				<PencilSquare className="size-4" strokeWidth="2" />
				{$i18n.t('New Chat')}
			</button>
			<button
				class="flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition text-sm text-gray-700 dark:text-gray-300"
				on:click={handleImport}
			>
				<svg class="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
				</svg>
				{$i18n.t('Import')}
			</button>
		</div>

		<!-- Search -->
		<div class="flex-shrink-0 px-4 py-2">
			<button
				class="flex items-center gap-2 w-full px-3 py-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-sm"
				on:click={async () => {
					await closeDrawer();
					showSearch.set(true);
				}}
			>
				<Search className="size-4" />
				{$i18n.t('Search chats...')}
			</button>
		</div>

		<!-- Chat List -->
		<div class="flex-1 overflow-y-auto px-2 pb-[env(safe-area-inset-bottom)]">
			<!-- Pinned Chats -->
			{#if $pinnedChats && $pinnedChats.length > 0}
				<div class="py-2">
					<Folder
						bind:open={showPinnedChat}
						name={$i18n.t('Pinned')}
					>
						<div class="ml-3 pl-1 mt-[1px] flex flex-col border-s border-gray-100 dark:border-gray-800">
							{#each $pinnedChats as chat, idx (`mobile-pinned-${chat?.id ?? idx}`)}
								<ChatItem
									className=""
									id={chat.id}
									title={chat.title}
									{shiftKey}
									selected={selectedChatId === chat.id}
									on:select={() => { selectedChatId = chat.id; }}
									on:unselect={() => { selectedChatId = null; }}
									on:change={async () => { await initChatList(); }}
									on:tag={(e) => {
										const { type, name } = e.detail;
										tagEventHandler(type, name, chat.id);
									}}
								/>
							{/each}
						</div>
					</Folder>
				</div>
			{/if}

			<!-- Regular Chats -->
			<div class="py-2">
				{#if $chats === null}
					<div class="w-full flex justify-center py-4 text-xs animate-pulse items-center gap-2">
						<Spinner className="size-4" />
						<div>{$i18n.t('Loading...')}</div>
					</div>
				{:else if $chats.length === 0}
					<div class="flex flex-col items-center justify-center py-8 text-gray-500">
						<div class="text-4xl mb-2">💬</div>
						<div class="text-sm">{$i18n.t('No chats yet')}</div>
						<div class="text-xs mt-1 text-center px-4">
							{$i18n.t('Start a new conversation')}
						</div>
					</div>
				{:else}
					{#each $chats as chat, idx (`mobile-chat-${chat?.id ?? idx}`)}
						{#if idx === 0 || (idx > 0 && chat.time_range !== $chats[idx - 1].time_range)}
							<div class="w-full pl-2.5 text-xs text-gray-500 dark:text-gray-500 font-medium {idx === 0 ? '' : 'pt-4'} pb-1.5">
								{$i18n.t(chat.time_range)}
							</div>
						{/if}

						<ChatItem
							className=""
							id={chat.id}
							title={chat.title}
							{shiftKey}
							selected={selectedChatId === chat.id}
							on:select={() => { selectedChatId = chat.id; }}
							on:unselect={() => { selectedChatId = null; }}
							on:change={async () => { await initChatList(); }}
							on:tag={(e) => {
								const { type, name } = e.detail;
								tagEventHandler(type, name, chat.id);
							}}
						/>
					{/each}

					{#if $scrollPaginationEnabled && !allChatsLoaded}
						<Loader
							on:visible={() => {
								if (!chatListLoading) {
									loadMoreChats();
								}
							}}
						>
							<div class="w-full flex justify-center py-2 text-xs animate-pulse items-center gap-2">
								<Spinner className="size-4" />
								<div>{$i18n.t('Loading...')}</div>
							</div>
						</Loader>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/if}

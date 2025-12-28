<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { goto, invalidate, invalidateAll } from '$app/navigation';
	import { onMount, getContext, createEventDispatcher, tick, onDestroy } from 'svelte';
	const i18n = getContext('i18n');

	const dispatch = createEventDispatcher();

	import {
		archiveChatById,
		cloneChatById,
		deleteChatById,
		getAllTags,
		getChatById,
		getChatList,
		getChatListByTagName,
		getPinnedChatList,
		updateChatById,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import {
		chatId,
		chatTitle as _chatTitle,
		chats,
		mobile,
		pinnedChats,
		showSidebar,
		currentChatPage,
		tags,
		selectedFolder
	} from '$lib/stores';

	import ChatMenu from './ChatMenu.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import ShareChatModal from '$lib/components/chat/ShareChatModal.svelte';
	import Drawer from '$lib/components/common/Drawer.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import DragGhost from '$lib/components/common/DragGhost.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import { generateTitle } from '$lib/apis';

	export let className = '';

	export let id;
	export let title;

	export let selected = false;
	export let shiftKey = false;

	export let onDragEnd = () => {};

	let chat = null;

	let mouseOver = false;
	let draggable = false;
	$: if (mouseOver) {
		loadChat();
	}

	const loadChat = async () => {
		if (!chat) {
			draggable = false;
			chat = await getChatById(localStorage.token, id);
			draggable = true;
		}
	};

	let showShareChatModal = false;
	let confirmEdit = false;
	let showRenameDrawer = false;  // 移动端重命名弹窗

	let chatTitle = title;
	let renameInputEl: HTMLInputElement;  // 弹窗内输入框引用

	const editChatTitle = async (id, title) => {
		if (title === '') {
			toast.error($i18n.t('Title cannot be an empty string.'));
		} else {
			await updateChatById(localStorage.token, id, {
				title: title
			});

			if (id === $chatId) {
				_chatTitle.set(title);
			}

			currentChatPage.set(1);
			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			await pinnedChats.set(await getPinnedChatList(localStorage.token));

			dispatch('change');
		}
	};

	const cloneChatHandler = async (id) => {
		const res = await cloneChatById(
			localStorage.token,
			id,
			$i18n.t('Clone of {{TITLE}}', {
				TITLE: title
			})
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			goto(`/c/${res.id}`);

			currentChatPage.set(1);
			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			await pinnedChats.set(await getPinnedChatList(localStorage.token));
		}
	};

	const deleteChatHandler = async (id) => {
		const res = await deleteChatById(localStorage.token, id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			tags.set(await getAllTags(localStorage.token));
			if ($chatId === id) {
				await goto('/');

				await chatId.set('');
				await tick();
			}

			dispatch('change');
		}
	};

	const archiveChatHandler = async (id) => {
		await archiveChatById(localStorage.token, id);
		dispatch('change');
	};

	const moveChatHandler = async (chatId, folderId) => {
		if (chatId && folderId) {
			const res = await updateChatFolderIdById(localStorage.token, chatId, folderId).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);

			if (res) {
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
				await pinnedChats.set(await getPinnedChatList(localStorage.token));

				dispatch('change');

				toast.success($i18n.t('Chat moved successfully'));
			}
		} else {
			toast.error($i18n.t('Failed to move chat'));
		}
	};

	let itemElement;

	let generating = false;

	let ignoreBlur = false;
	let doubleClicked = false;

	let dragged = false;
	let x = 0;
	let y = 0;

	// 移动端触摸处理
	let touchStartY = 0;
	let touchStartX = 0;
	let touchStartTime = 0;

	const handleTouchStart = (e: TouchEvent) => {
		if (!$mobile) return;
		touchStartY = e.touches[0].clientY;
		touchStartX = e.touches[0].clientX;
		touchStartTime = Date.now();
	};

	const handleTouchEnd = (e: TouchEvent) => {
		if (!$mobile) return;

		const touchEndY = e.changedTouches[0].clientY;
		const touchEndX = e.changedTouches[0].clientX;
		const touchDuration = Date.now() - touchStartTime;
		const deltaY = Math.abs(touchEndY - touchStartY);
		const deltaX = Math.abs(touchEndX - touchStartX);

		// 如果移动距离小于 10px 且时间小于 500ms，认为是点击而不是滚动
		if (deltaY < 10 && deltaX < 10 && touchDuration < 500) {
			e.preventDefault();
			dispatch('select');
			showSidebar.set(false);
			goto(`/c/${id}`);
		}
	};

	const dragImage = new Image();
	dragImage.src =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

	const onDragStart = (event) => {
		event.stopPropagation();

		event.dataTransfer.setDragImage(dragImage, 0, 0);

		// Set the data to be transferred
		event.dataTransfer.setData(
			'text/plain',
			JSON.stringify({
				type: 'chat',
				id: id,
				item: chat
			})
		);

		dragged = true;
		itemElement.style.opacity = '0.5'; // Optional: Visual cue to show it's being dragged
	};

	const onDrag = (event) => {
		event.stopPropagation();

		x = event.clientX;
		y = event.clientY;
	};

	const onDragEndHandler = (event) => {
		event.stopPropagation();

		itemElement.style.opacity = '1'; // Reset visual cue after drag
		dragged = false;

		onDragEnd(event);
	};

	const onClickOutside = (event) => {
		if (confirmEdit && !event.target.closest(`#chat-title-input-${id}`)) {
			confirmEdit = false;
			ignoreBlur = false;
			chatTitle = '';
		}
	};

	onMount(() => {
		if (itemElement) {
			document.addEventListener('click', onClickOutside, true);

			// Event listener for when dragging starts
			itemElement.addEventListener('dragstart', onDragStart);
			// Event listener for when dragging occurs (optional)
			itemElement.addEventListener('drag', onDrag);
			// Event listener for when dragging ends
			itemElement.addEventListener('dragend', onDragEndHandler);
		}
	});

	onDestroy(() => {
		if (itemElement) {
			document.removeEventListener('click', onClickOutside, true);

			itemElement.removeEventListener('dragstart', onDragStart);
			itemElement.removeEventListener('drag', onDrag);
			itemElement.removeEventListener('dragend', onDragEndHandler);
		}
	});

	let showDeleteConfirm = false;

	const chatTitleInputKeydownHandler = (e) => {
		if (e.key === 'Enter') {
			e.preventDefault();
			setTimeout(() => {
				const input = document.getElementById(`chat-title-input-${id}`);
				if (input) input.blur();
			}, 0);
		} else if (e.key === 'Escape') {
			e.preventDefault();
			confirmEdit = false;
			chatTitle = '';
		}
	};

	const renameHandler = async () => {
		chatTitle = title;

		if ($mobile) {
			// 移动端使用底部弹窗
			showRenameDrawer = true;
		} else {
			// 桌面端使用内联编辑
			confirmEdit = true;

			await tick();

			setTimeout(() => {
				const input = document.getElementById(`chat-title-input-${id}`);
				if (input) {
					input.focus();
				}
			}, 0);
		}
	};

	// 移动端弹窗内确认重命名
	const confirmRename = async () => {
		if (chatTitle !== '' && chatTitle !== title) {
			await editChatTitle(id, chatTitle);
		}
		showRenameDrawer = false;
		chatTitle = '';
	};

	// 移动端弹窗内取消重命名
	const cancelRename = () => {
		showRenameDrawer = false;
		chatTitle = '';
	};

	const generateTitleHandler = async () => {
		generating = true;
		if (!chat) {
			chat = await getChatById(localStorage.token, id);
		}

		const messages = (chat.chat?.messages ?? []).map((message) => {
			return {
				role: message.role,
				content: message.content
			};
		});

		const model = chat.chat.models.at(0) ?? chat.models.at(0) ?? '';

		chatTitle = '';

		const generatedTitle = await generateTitle(localStorage.token, model, messages).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (generatedTitle) {
			if (generatedTitle !== title) {
				editChatTitle(id, generatedTitle);
			}

			confirmEdit = false;
		} else {
			chatTitle = title;
		}

		generating = false;
	};
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={id} />

<!-- 移动端重命名弹窗 -->
<Drawer bind:show={showRenameDrawer} className="rounded-t-2xl">
	<div class="p-4 pb-6">
		<div class="flex items-center justify-between mb-4">
			<h3 class="text-lg font-semibold">{$i18n.t('Rename')}</h3>
			<button
				class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition"
				on:click={cancelRename}
			>
				<XMark className="size-5" />
			</button>
		</div>

		<input
			bind:this={renameInputEl}
			bind:value={chatTitle}
			class="w-full px-4 py-3 rounded-xl border-2 border-blue-500 dark:border-blue-400 bg-white dark:bg-gray-800 text-base outline-none transition"
			placeholder={$i18n.t('点击此处输入新标题')}
			on:keydown={(e) => {
				if (e.key === 'Enter') {
					e.preventDefault();
					confirmRename();
				}
			}}
		/>

		<div class="flex gap-3 mt-4">
			<button
				class="flex-1 px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition font-medium"
				on:click={cancelRename}
			>
				{$i18n.t('Cancel')}
			</button>
			<button
				class="flex-1 px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition font-medium disabled:opacity-50 disabled:cursor-not-allowed"
				on:click={confirmRename}
				disabled={chatTitle === '' || chatTitle === title}
			>
				{$i18n.t('Confirm')}
			</button>
		</div>
	</div>
</Drawer>

<DeleteConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete chat?')}
	on:confirm={() => {
		deleteChatHandler(id);
	}}
>
	<div class=" text-sm text-gray-500 flex-1 line-clamp-3">
		{$i18n.t('This will delete')} <span class="  font-semibold">{title}</span>.
	</div>
</DeleteConfirmDialog>

{#if dragged && x && y}
	<DragGhost {x} {y}>
		<div class=" bg-black/80 backdrop-blur-2xl px-2 py-1 rounded-lg w-fit max-w-40">
			<div class="flex items-center gap-1">
				<Document className=" size-[18px]" strokeWidth="2" />
				<div class=" text-xs text-white line-clamp-1">
					{title}
				</div>
			</div>
		</div>
	</DragGhost>
{/if}

<div
	id="sidebar-chat-group"
	bind:this={itemElement}
	class=" w-full {className} relative group"
	draggable={draggable && !confirmEdit}
>
	{#if confirmEdit}
		<div
			id="sidebar-chat-item"
			class=" w-full flex justify-between rounded-xl px-[11px] py-3 {id === $chatId ||
			confirmEdit
				? 'bg-gray-100 dark:bg-gray-900 selected'
				: selected
					? 'bg-gray-100 dark:bg-gray-950 selected'
					: 'group-hover:bg-gray-100 dark:group-hover:bg-gray-950'}  whitespace-nowrap text-ellipsis relative {generating
				? 'cursor-not-allowed'
				: ''}"
		>
			<input
				id="chat-title-input-{id}"
				bind:value={chatTitle}
				class=" bg-transparent w-full outline-hidden mr-16 border-b border-blue-500 dark:border-blue-400"
				placeholder={generating ? $i18n.t('Generating...') : ''}
				disabled={generating}
				on:keydown={chatTitleInputKeydownHandler}
				on:blur={async (e) => {
					// check if target is generate button
					if (ignoreBlur) {
						ignoreBlur = false;

						if (e.relatedTarget?.id === 'generate-title-button') {
							generateTitleHandler();
						}
						return;
					}

					if (doubleClicked) {
						e.preventDefault();
						e.stopPropagation();

						await tick();
						setTimeout(() => {
							const input = document.getElementById(`chat-title-input-${id}`);
							if (input) input.focus();
						}, 0);

						doubleClicked = false;
						return;
					}

					if (chatTitle !== title) {
						editChatTitle(id, chatTitle);
					}

					confirmEdit = false;
					chatTitle = '';
				}}
			/>
		</div>
	{:else}
		<a
			id="sidebar-chat-item"
			class=" w-full flex justify-between rounded-xl px-[11px] py-3 {id === $chatId ||
			confirmEdit
				? 'bg-gray-100 dark:bg-gray-900 selected'
				: selected
					? 'bg-gray-100 dark:bg-gray-950 selected'
					: ' group-hover:bg-gray-100 dark:group-hover:bg-gray-950'}  whitespace-nowrap text-ellipsis"
			href="/c/{id}"
			on:click={() => {
				dispatch('select');

				if ($selectedFolder) {
					selectedFolder.set(null);
				}

				if ($mobile) {
					showSidebar.set(false);
				}
			}}
			on:dblclick={async (e) => {
				if ($mobile) return;
				e.preventDefault();
				e.stopPropagation();

				doubleClicked = true;
				renameHandler();
			}}
			on:mouseenter={(e) => {
				if (!$mobile) mouseOver = true;
			}}
			on:mouseleave={(e) => {
				if (!$mobile) mouseOver = false;
			}}
			on:focus={(e) => {}}
			on:touchstart={handleTouchStart}
			on:touchend={handleTouchEnd}
			draggable="false"
		>
			<div class=" flex self-center flex-1 w-full">
				<div dir="auto" class="text-left self-center overflow-hidden w-full h-[20px] truncate">
					{title}
				</div>
			</div>
		</a>
	{/if}

	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		id="sidebar-chat-item-menu"
		class="
        {id === $chatId || confirmEdit
			? 'from-gray-100 dark:from-gray-900 selected'
			: selected
				? 'from-gray-100 dark:from-gray-950 selected'
				: $mobile
					? ''
					: 'invisible group-hover:visible from-gray-100 dark:from-gray-950'}
            absolute {className === 'pr-2'
			? 'right-[8px]'
			: 'right-1'} top-[4px] py-1 pr-0.5 mr-1.5 {$mobile ? 'pl-0' : 'pl-5 bg-linear-to-l from-80% to-transparent'}
			z-10"
		on:mouseenter={(e) => {
			if (!$mobile) mouseOver = true;
		}}
		on:mouseleave={(e) => {
			if (!$mobile) mouseOver = false;
		}}
		on:touchstart|stopPropagation
		on:touchend|stopPropagation
		on:click|stopPropagation
	>
		{#if confirmEdit}
			<div
				class="flex self-center items-center space-x-1 z-10"
			>
				<!-- 确认按钮 -->
				<button
					class="self-center p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition text-green-600 dark:text-green-400"
					on:click|stopPropagation={() => {
						if (chatTitle !== title && chatTitle !== '') {
							editChatTitle(id, chatTitle);
						}
						confirmEdit = false;
						chatTitle = '';
					}}
					on:touchend|stopPropagation|preventDefault={() => {
						if (chatTitle !== title && chatTitle !== '') {
							editChatTitle(id, chatTitle);
						}
						confirmEdit = false;
						chatTitle = '';
					}}
					type="button"
				>
					<Check className="size-4" strokeWidth="2.5" />
				</button>

				<!-- 取消按钮 -->
				<button
					class="self-center p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition text-red-500"
					on:click|stopPropagation={() => {
						confirmEdit = false;
						chatTitle = '';
					}}
					on:touchend|stopPropagation|preventDefault={() => {
						confirmEdit = false;
						chatTitle = '';
					}}
					type="button"
				>
					<XMark className="size-4" strokeWidth="2.5" />
				</button>
			</div>
		{:else if shiftKey && mouseOver}
			<div class=" flex items-center self-center space-x-1.5">
				<Tooltip content={$i18n.t('Archive')} className="flex items-center">
					<button
						class=" self-center dark:hover:text-white transition"
						on:click={() => {
							archiveChatHandler(id);
						}}
						type="button"
					>
						<ArchiveBox className="size-4  translate-y-[0.5px]" strokeWidth="2" />
					</button>
				</Tooltip>

				<Tooltip content={$i18n.t('Delete')}>
					<button
						class=" self-center dark:hover:text-white transition"
						on:click={() => {
							deleteChatHandler(id);
						}}
						type="button"
					>
						<GarbageBin strokeWidth="2" />
					</button>
				</Tooltip>
			</div>
		{:else}
			<div class="flex self-center z-10 items-end">
				<ChatMenu
					chatId={id}
					cloneChatHandler={() => {
						cloneChatHandler(id);
					}}
					shareHandler={() => {
						showShareChatModal = true;
					}}
					{moveChatHandler}
					archiveChatHandler={() => {
						archiveChatHandler(id);
					}}
					{renameHandler}
					deleteHandler={() => {
						showDeleteConfirm = true;
					}}
					onClose={() => {
						dispatch('unselect');
					}}
					on:change={async () => {
						dispatch('change');
					}}
					on:tag={(e) => {
						dispatch('tag', e.detail);
					}}
				>
					<button
						aria-label="Chat Menu"
						class=" self-center dark:hover:text-white transition m-0"
						on:click={() => {
							dispatch('select');
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				</ChatMenu>

				{#if id === $chatId}
					<!-- Shortcut support using "delete-chat-button" id -->
					<button
						id="delete-chat-button"
						class="hidden"
						on:click={() => {
							showDeleteConfirm = true;
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>

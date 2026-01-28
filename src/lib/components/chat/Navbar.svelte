<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		WEBUI_NAME,
		banners,
		chatId,
		config,
		mobile,
		settings,
		showArchivedChats,
		showControls,
		showSidebar,
		showMobileUserPanel,
		showMobileChatDrawer,
		temporaryChatEnabled,
		user
	} from '$lib/stores';

	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	import ShareChatModal from '../chat/ShareChatModal.svelte';
	import ModelSelector from '../chat/ModelSelector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Menu from '$lib/components/layout/Navbar/Menu.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import AdjustmentsHorizontal from '../icons/AdjustmentsHorizontal.svelte';

	import PencilSquare from '../icons/PencilSquare.svelte';
	import Banner from '../common/Banner.svelte';
	import Sidebar from '../icons/Sidebar.svelte';

	import ChatBubbleDotted from '../icons/ChatBubbleDotted.svelte';
	import ChatBubbleDottedChecked from '../icons/ChatBubbleDottedChecked.svelte';

	import EllipsisHorizontal from '../icons/EllipsisHorizontal.svelte';
	import ChatPlus from '../icons/ChatPlus.svelte';
	import ChatCheck from '../icons/ChatCheck.svelte';
	import Knobs from '../icons/Knobs.svelte';

	import { getChatErrorMessages } from '$lib/apis/chats';
	import ErrorListModal from './ErrorListModal.svelte';
	import ErrorDetailModal from './ErrorDetailModal.svelte';

	const i18n = getContext('i18n');

	export let initNewChat: Function;
	export let shareEnabled: boolean = false;

	export let chat;
	export let history;
	export let selectedModels;
	export let showModelSelector = true;

	// Session-specific model name customization
	export let customModelNames = {};
	export let onRenameModel: (modelId: string, customName: string) => void = () => {};

	export let onSaveTempChat: () => {};
	export let archiveChatHandler: (id: string) => void;
	export let moveChatHandler: (id: string, folderId: string) => void;

	let closedBannerIds = [];

	let showShareChatModal = false;
	let showDownloadChatModal = false;

	// Error messages state
	let errorMessages = null;
	let showErrorListModal = false;
	let showErrorDetailModal = false;
	let selectedError = null;
	let selectedErrorIndex = 0;

	// Load error messages when chat changes
	const loadErrorMessages = async (chatId: string) => {
		if (!chatId || !$user?.role || $user.role !== 'admin') {
			errorMessages = null;
			return;
		}

		try {
			const res = await getChatErrorMessages(localStorage.token, chatId);
			errorMessages = res;
		} catch (err) {
			console.error('Failed to load error messages:', err);
			errorMessages = null;
		}
	};

	$: if ($chatId && $user?.role === 'admin') {
		loadErrorMessages($chatId);
	} else {
		errorMessages = null;
	}
</script>

<ShareChatModal bind:show={showShareChatModal} chatId={$chatId} />

<button
	id="new-chat-button"
	class="hidden"
	on:click={() => {
		initNewChat();
	}}
	aria-label="New Chat"
/>

<nav class="sticky top-0 z-30 w-full py-1 -mb-8 flex flex-col items-center drag-region">
	<div class="flex items-center w-full pl-1.5 pr-1">
		<div
			class=" bg-linear-to-b via-40% to-97% from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pointer-events-none absolute inset-0 -bottom-7 z-[-1]"
		></div>

		<div class=" flex max-w-full w-full mx-auto px-1.5 md:px-2 pt-0.5 bg-transparent">
			<div class="flex items-center w-full max-w-full">
				{#if $mobile}
					<!-- Mobile: User menu button -->
					<div
						class="-translate-x-0.5 mr-1 mt-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
					>
						<Tooltip content={$i18n.t('Menu')}>
							<button
								class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showMobileUserPanel.set(true);
								}}
							>
								<div class="self-center p-1.5">
									{#if $user?.profile_image_url}
										<img
											src={$user.profile_image_url}
											class="size-6 object-cover rounded-full"
											alt=""
											draggable="false"
										/>
									{:else}
										<Sidebar />
									{/if}
								</div>
							</button>
						</Tooltip>
					</div>
				{:else if !$showSidebar}
					<!-- Desktop: Sidebar toggle button -->
					<div
						class="-translate-x-0.5 mr-1 mt-1 self-start flex flex-none items-center text-gray-600 dark:text-gray-400"
					>
						<Tooltip content={$i18n.t('Open Sidebar')}>
							<button
								class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showSidebar.set(true);
								}}
							>
								<div class="self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div
					class="flex-1 overflow-hidden max-w-full py-0.5
			{$showSidebar ? 'ml-1' : ''}
			"
				>
					{#if showModelSelector}
						<ModelSelector
							bind:selectedModels
							showSetDefault={!shareEnabled}
							{customModelNames}
							{onRenameModel}
						/>
					{/if}
				</div>

				<div class="self-start flex flex-none items-center text-gray-600 dark:text-gray-400">
					<!-- Mobile: Chat drawer button -->
					{#if $mobile}
						<Tooltip content={$i18n.t('Chats')}>
							<button
								class="cursor-pointer flex px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={() => {
									showMobileChatDrawer.set(true);
								}}
							>
								<div class="m-auto self-center">
									<svg class="size-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
									</svg>
								</div>
							</button>
						</Tooltip>
					{/if}

					<!-- Admin: Error messages button -->
					{#if $user?.role === 'admin' && errorMessages?.error_messages?.length > 0}
						<Tooltip content="错误日志">
							<button
								class="cursor-pointer flex px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition relative"
								on:click={() => {
									showErrorListModal = true;
								}}
							>
								<div class="m-auto self-center">
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										class="size-5 text-red-500"
									>
										<path
											fill-rule="evenodd"
											d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
								<!-- Error count badge -->
								<div
									class="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1"
								>
									{errorMessages.error_messages.length}
								</div>
							</button>
						</Tooltip>
					{/if}
					<!-- <div class="md:hidden flex self-center w-[1px] h-5 mx-2 bg-gray-300 dark:bg-stone-700" /> -->

					<!-- ai-friend 	屏蔽临时聊天 -->
					{#if $user?.role === 'user' ? ($user?.permissions?.chat?.temporary ?? true) && !($user?.permissions?.chat?.temporary_enforced ?? false) : true}
						{#if !chat?.id}
							{#if false}
								<Tooltip content={$i18n.t(`Temporary Chat`)}>
									<button
										class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
										id="temporary-chat-button"
										on:click={async () => {
											if (($settings?.temporaryChatByDefault ?? false) && $temporaryChatEnabled) {
												// for proper initNewChat handling
												await temporaryChatEnabled.set(null);
											} else {
												await temporaryChatEnabled.set(!$temporaryChatEnabled);
											}

											await goto('/');

											// add 'temporary-chat=true' to the URL
											if ($temporaryChatEnabled) {
												window.history.replaceState(null, '', '?temporary-chat=true');
											} else {
												window.history.replaceState(null, '', location.pathname);
											}
										}}
									>
										<div class=" m-auto self-center">
											{#if $temporaryChatEnabled}
												<ChatBubbleDottedChecked className=" size-4.5" strokeWidth="1.5" />
											{:else}
												<ChatBubbleDotted className=" size-4.5" strokeWidth="1.5" />
											{/if}
										</div>
									</button>
								</Tooltip>
							{/if}
						{:else if $temporaryChatEnabled}
							<Tooltip content={$i18n.t(`Save Chat`)}>
								<button
									class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
									id="save-temporary-chat-button"
									on:click={async () => {
										onSaveTempChat();
									}}
								>
									<div class=" m-auto self-center">
										<ChatCheck className=" size-4.5" strokeWidth="1.5" />
									</div>
								</button>
							</Tooltip>
						{/if}
					{/if}

					<!-- {#if $mobile && !$temporaryChatEnabled && chat && chat.id}
						<Tooltip content={$i18n.t('New Chat')}>
							<button
								class=" flex {$showSidebar
									? 'md:hidden'
									: ''} cursor-pointer px-2 py-2 rounded-xl text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								on:click={() => {
									initNewChat();
								}}
								aria-label="New Chat"
							>
								<div class=" m-auto self-center">
									<ChatPlus className=" size-4.5" strokeWidth="1.5" />
								</div>
							</button>
						</Tooltip>
					{/if} -->

					<!-- {#if shareEnabled && chat && (chat.id || $temporaryChatEnabled)}
						<Menu
							{chat}
							{shareEnabled}
							shareHandler={() => {
								showShareChatModal = !showShareChatModal;
							}}
							archiveChatHandler={() => {
								archiveChatHandler(chat.id);
							}}
							{moveChatHandler}
						>
							<button
								class="flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
								id="chat-context-menu-button"
							>
								<div class=" m-auto self-center">
									<EllipsisHorizontal className=" size-5" strokeWidth="1.5" />
								</div>
							</button>
						</Menu>
					{/if} -->

					<!-- ai-friend 	屏蔽对话高级设置 -->
					{#if false}
						{#if $user?.role === 'admin' || ($user?.permissions.chat?.controls ?? true)}
							<Tooltip content={$i18n.t('Controls')}>
								<button
									class=" flex cursor-pointer px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-850 transition"
									on:click={async () => {
										await showControls.set(!$showControls);
									}}
									aria-label="Controls"
								>
									<div class=" m-auto self-center">
										<Knobs className=" size-5" strokeWidth="1" />
									</div>
								</button>
							</Tooltip>
						{/if}
					{/if}

					<!-- {#if $user !== undefined && $user !== null}
						<UserMenu
							className="max-w-[240px]"
							role={$user?.role}
							help={true}
							on:show={(e) => {
								if (e.detail === 'archived-chat') {
									showArchivedChats.set(true);
								}
							}}
						>
							<div
								class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							>
								<div class=" self-center">
									<span class="sr-only">{$i18n.t('User menu')}</span>
									<img
										src={$user?.profile_image_url}
										class="size-6 object-cover rounded-full"
										alt=""
										draggable="false"
									/>
								</div>
							</div>
						</UserMenu>
					{/if} -->
				</div>
			</div>
		</div>
	</div>

	{#if $temporaryChatEnabled && ($chatId ?? '').startsWith('local:')}
		<div class=" w-full z-30 text-center">
			<div class="text-xs text-gray-500">{$i18n.t('Temporary Chat')}</div>
		</div>
	{/if}

	<div class="absolute top-[100%] left-0 right-0 h-fit">
		{#if !history.currentId && !$chatId && ($banners.length > 0 || ($config?.license_metadata?.type ?? null) === 'trial' || (($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats))}
			<div class=" w-full z-30">
				<div class=" flex flex-col gap-1 w-full">
					{#if ($config?.license_metadata?.type ?? null) === 'trial'}
						<Banner
							banner={{
								type: 'info',
								title: 'Trial License',
								content: $i18n.t(
									'You are currently using a trial license. Please contact support to upgrade your license.'
								)
							}}
						/>
					{/if}

					{#if ($config?.license_metadata?.seats ?? null) !== null && $config?.user_count > $config?.license_metadata?.seats}
						<Banner
							banner={{
								type: 'error',
								title: 'License Error',
								content: $i18n.t(
									'Exceeded the number of seats in your license. Please contact support to increase the number of seats.'
								)
							}}
						/>
					{/if}

					{#each $banners.filter((b) => ![...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]'), ...closedBannerIds].includes(b.id)) as banner (banner.id)}
						<Banner
							{banner}
							on:dismiss={(e) => {
								const bannerId = e.detail;

								if (banner.dismissible) {
									localStorage.setItem(
										'dismissedBannerIds',
										JSON.stringify(
											[
												bannerId,
												...JSON.parse(localStorage.getItem('dismissedBannerIds') ?? '[]')
											].filter((id) => $banners.find((b) => b.id === id))
										)
									);
								} else {
									closedBannerIds = [...closedBannerIds, bannerId];
								}
							}}
						/>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</nav>

<!-- Error Modals -->
<ErrorListModal
	bind:show={showErrorListModal}
	errorMessages={errorMessages?.error_messages || []}
	on:select={(e) => {
		selectedError = e.detail.error;
		selectedErrorIndex = e.detail.index;
		showErrorListModal = false;
		showErrorDetailModal = true;
	}}
/>

<ErrorDetailModal
	bind:show={showErrorDetailModal}
	error={selectedError}
	errorIndex={selectedErrorIndex}
/>

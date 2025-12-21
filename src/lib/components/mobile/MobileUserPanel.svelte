<script lang="ts">
	import { getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';

	import { userSignOut } from '$lib/apis/auths';
	import { getBalance } from '$lib/apis/billing';

	import {
		showSettings,
		showMobileUserPanel,
		showShortcuts,
		showArchivedChats,
		showAnnouncements,
		user,
		balance
	} from '$lib/stores';

	import SlidePanel from '$lib/components/common/SlidePanel.svelte';
	import BalanceDisplay from '$lib/components/billing/BalanceDisplay.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import SignOut from '$lib/components/icons/SignOut.svelte';
	import Code from '$lib/components/icons/Code.svelte';
	import UserGroup from '$lib/components/icons/UserGroup.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';

	const i18n = getContext('i18n');

	const loadBalance = async () => {
		try {
			const balanceInfo = await getBalance(localStorage.token);
			balance.set(balanceInfo);
		} catch (error) {
			console.error('Error fetching balance:', error);
		}
	};

	$: if ($showMobileUserPanel) {
		loadBalance();
	}

	const closePanel = async () => {
		await tick();
		showMobileUserPanel.set(false);
	};

	const handleNavigation = async (path: string) => {
		await closePanel();
		goto(path);
	};

	const handleAction = async (action: () => void) => {
		await closePanel();
		action();
	};

	const handleSignOut = async () => {
		const res = await userSignOut();
		user.set(null);
		localStorage.removeItem('token');
		location.href = res?.redirect_url ?? '/auth';
	};
</script>

<SlidePanel bind:show={$showMobileUserPanel}>
	<div class="flex flex-col h-full">
		<!-- User Info Header -->
		<div class="p-4 border-b border-gray-100 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<img
					src={$user?.profile_image_url}
					class="size-12 object-cover rounded-full"
					alt=""
					draggable="false"
				/>
				<div class="flex-1 min-w-0">
					<div class="font-medium text-gray-900 dark:text-white truncate">
						{$user?.name || 'User'}
					</div>
					<div class="text-sm text-gray-500 dark:text-gray-400 truncate">
						{$user?.email || ''}
					</div>
				</div>
			</div>
		</div>

		<!-- Balance Display -->
		<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-800">
			<BalanceDisplay compact={true} />
		</div>

		<!-- Menu Items -->
		<div class="flex-1 overflow-y-auto">
			<div class="py-2">
				<!-- Billing -->
				<button
					class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => handleNavigation('/billing')}
				>
					<svg
						class="w-5 h-5 text-gray-600 dark:text-gray-400"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="1.5"
							d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
					<span class="text-gray-900 dark:text-white">{$i18n.t('计费中心')}</span>
				</button>

				<div class="h-px bg-gray-100 dark:bg-gray-800 mx-4 my-1" />

				<!-- Memory -->
				<button
					class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => handleNavigation('/memories')}
				>
					<Sparkles className="size-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
					<span class="text-gray-900 dark:text-white">{$i18n.t('Memory')}</span>
				</button>

				<!-- Archived Chats -->
				<button
					class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => handleAction(() => showArchivedChats.set(true))}
				>
					<ArchiveBox className="size-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
					<span class="text-gray-900 dark:text-white">{$i18n.t('Archived Chats')}</span>
				</button>

				<!-- Admin Only -->
				{#if $user?.role === 'admin'}
					<div class="h-px bg-gray-100 dark:bg-gray-800 mx-4 my-1" />

					<button
						class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						on:click={() => handleNavigation('/playground')}
					>
						<Code className="size-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
						<span class="text-gray-900 dark:text-white">{$i18n.t('Playground')}</span>
					</button>

					<button
						class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						on:click={() => handleNavigation('/admin')}
					>
						<UserGroup className="w-5 h-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
						<span class="text-gray-900 dark:text-white">{$i18n.t('Admin Panel')}</span>
					</button>

					<button
						class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						on:click={() => handleNavigation('/announcements/manage')}
					>
						<svg
							class="w-5 h-5 text-gray-600 dark:text-gray-400"
							viewBox="0 0 1024 1024"
							fill="currentColor"
						>
							<path
								d="M256.8 577.056l512.512 0c17.696 0 32-14.304 32-32s-14.304-32-32-32L256.8 513.056c-17.696 0-32 14.304-32 32S239.136 577.056 256.8 577.056z"
							/>
							<path
								d="M256.8 769.056l512.512 0c17.696 0 32-14.304 32-32s-14.304-32-32-32L256.8 705.056c-17.696 0-32 14.304-32 32S239.136 769.056 256.8 769.056z"
							/>
							<path
								d="M448 192l160 0c17.696 0 32-14.304 32-32s-14.304-32-32-32l-160 0c-17.696 0-32 14.304-32 32S430.304 192 448 192z"
							/>
							<path
								d="M847.008 128 800 128c-17.696 0-32 14.304-32 32s14.304 32 32 32l47.008 0C852.992 192 864 204.16 864 224l0 96L160 320 160 224c0-17.664 14.048-32 31.328-32L256 192c17.696 0 32-14.304 32-32S273.696 128 256 128L191.328 128C138.752 128 96 171.072 96 224l0 640c0 52.928 43.072 96 96 96l640 0c52.928 0 96-43.072 96-96L928 224C928 171.072 891.648 128 847.008 128zM864 864c0 17.664-14.368 32-32 32L192 896c-17.632 0-32-14.336-32-32L160 384l704 0L864 864z"
							/>
							<path
								d="M704 224c17.696 0 32-14.304 32-32L736 96c0-17.696-14.304-32-32-32s-32 14.304-32 32l0 96C672 209.696 686.304 224 704 224z"
							/>
							<path
								d="M352 224c17.696 0 32-14.304 32-32L384 96c0-17.696-14.304-32-32-32s-32 14.304-32 32l0 96C320 209.696 334.304 224 352 224z"
							/>
						</svg>
						<span class="text-gray-900 dark:text-white">{$i18n.t('公告管理')}</span>
					</button>
				{:else}
					<!-- Announcements for non-admin -->
					<button
						class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
						on:click={() => handleAction(() => showAnnouncements.set(true))}
					>
						<svg
							class="w-5 h-5 text-gray-600 dark:text-gray-400"
							viewBox="0 0 1024 1024"
							fill="currentColor"
						>
							<path
								d="M256.8 577.056l512.512 0c17.696 0 32-14.304 32-32s-14.304-32-32-32L256.8 513.056c-17.696 0-32 14.304-32 32S239.136 577.056 256.8 577.056z"
							/>
							<path
								d="M256.8 769.056l512.512 0c17.696 0 32-14.304 32-32s-14.304-32-32-32L256.8 705.056c-17.696 0-32 14.304-32 32S239.136 769.056 256.8 769.056z"
							/>
							<path
								d="M448 192l160 0c17.696 0 32-14.304 32-32s-14.304-32-32-32l-160 0c-17.696 0-32 14.304-32 32S430.304 192 448 192z"
							/>
							<path
								d="M847.008 128 800 128c-17.696 0-32 14.304-32 32s14.304 32 32 32l47.008 0C852.992 192 864 204.16 864 224l0 96L160 320 160 224c0-17.664 14.048-32 31.328-32L256 192c17.696 0 32-14.304 32-32S273.696 128 256 128L191.328 128C138.752 128 96 171.072 96 224l0 640c0 52.928 43.072 96 96 96l640 0c52.928 0 96-43.072 96-96L928 224C928 171.072 891.648 128 847.008 128zM864 864c0 17.664-14.368 32-32 32L192 896c-17.632 0-32-14.336-32-32L160 384l704 0L864 864z"
							/>
							<path
								d="M704 224c17.696 0 32-14.304 32-32L736 96c0-17.696-14.304-32-32-32s-32 14.304-32 32l0 96C672 209.696 686.304 224 704 224z"
							/>
							<path
								d="M352 224c17.696 0 32-14.304 32-32L384 96c0-17.696-14.304-32-32-32s-32 14.304-32 32l0 96C320 209.696 334.304 224 352 224z"
							/>
						</svg>
						<span class="text-gray-900 dark:text-white">{$i18n.t('公告')}</span>
					</button>
				{/if}

				<!-- Settings -->
				<button
					class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => handleAction(() => showSettings.set(true))}
				>
					<Settings className="w-5 h-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
					<span class="text-gray-900 dark:text-white">{$i18n.t('Settings')}</span>
				</button>

				<div class="h-px bg-gray-100 dark:bg-gray-800 mx-4 my-1" />

				<!-- Feedback -->
				<button
					class="flex items-center gap-3 w-full px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => handleNavigation('/feedback')}
				>
					<svg
						class="w-5 h-5 text-gray-600 dark:text-gray-400"
						viewBox="0 0 1024 1024"
						fill="currentColor"
					>
						<path
							d="M931.302 94.293L960 122.99v360.313l-28.698 28.698H822.89L714.477 623.602l-51.018-22.32v-89.281h-63.772l3.189-28.698-3.189-31.886h121.167v76.527l76.527-76.527h105.224v-299.73H363.73v63.772l-31.886-3.189-28.698 3.189v-92.47l28.698-28.698h599.458v0.002zM446.633 658.677c29.76 12.754 56.332 30.823 79.715 54.206 23.383 23.383 41.452 52.081 54.206 86.093 10.629 23.383 17.006 46.766 19.132 70.149l3.189 60.584h-60.584v-31.886c0-27.635-5.314-53.675-15.943-78.121-10.629-24.446-25.509-46.766-44.641-66.961-19.132-20.195-41.452-35.606-66.961-46.235-25.509-10.629-52.081-15.943-79.715-15.943h-3.189c-27.635 0-54.206 5.314-79.715 15.943s-47.829 26.04-66.961 46.235c-19.132 20.195-34.012 42.515-44.641 66.961-10.629 24.446-15.943 50.486-15.943 78.121v31.886H64l3.189-57.395c2.126-25.509 7.44-49.955 15.943-73.338 14.88-34.012 34.012-62.709 57.395-86.093s48.892-41.452 76.527-54.206c-27.635-19.132-49.955-44.109-66.961-74.932s-25.509-64.835-25.509-102.036 9.034-71.744 27.103-103.63 43.578-57.395 76.527-76.527 68.024-28.698 105.224-28.698 71.744 9.566 103.63 28.698 57.395 44.641 76.527 76.527 28.698 66.429 28.698 103.63-8.503 71.212-25.509 102.036c-17.007 30.823-40.39 55.8-70.151 74.932z m-114.79-28.697c42.515 0 78.121-14.349 106.819-43.046s43.046-63.772 43.046-105.224-14.349-76.527-43.046-105.224-63.772-43.046-105.224-43.046-76.527 14.349-105.224 43.046c-28.697 28.698-43.046 63.772-43.046 105.224s14.349 76.527 43.046 105.224 63.24 43.046 103.629 43.046z"
						/>
					</svg>
					<span class="text-gray-900 dark:text-white">{$i18n.t('反馈')}</span>
				</button>
			</div>
		</div>

		<!-- Sign Out -->
		<div class="border-t border-gray-100 dark:border-gray-800 p-4">
			<button
				class="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition"
				on:click={handleSignOut}
			>
				<SignOut className="w-5 h-5 text-gray-600 dark:text-gray-400" strokeWidth="1.5" />
				<span class="text-gray-900 dark:text-white">{$i18n.t('Sign Out')}</span>
			</button>
		</div>
	</div>
</SlidePanel>

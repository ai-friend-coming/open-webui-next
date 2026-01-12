<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { createEventDispatcher, getContext, onMount, tick } from 'svelte';

	import { flyAndScale } from '$lib/utils/transitions';
	import { goto } from '$app/navigation';
	import { fade, slide } from 'svelte/transition';

	import { getUsage } from '$lib/apis';
	import { userSignOut } from '$lib/apis/auths';
	import { logOutTracking } from '$lib/posthog';
	import { getBalance } from '$lib/apis/billing';

	import { showSettings, mobile, showSidebar, showShortcuts, user, balance } from '$lib/stores';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import ArchiveBox from '$lib/components/icons/ArchiveBox.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Map from '$lib/components/icons/Map.svelte';
	import Keyboard from '$lib/components/icons/Keyboard.svelte';
	import ShortcutsModal from '$lib/components/chat/ShortcutsModal.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import Code from '$lib/components/icons/Code.svelte';
	import UserGroup from '$lib/components/icons/UserGroup.svelte';
	import SignOut from '$lib/components/icons/SignOut.svelte';
	import BalanceDisplay from '$lib/components/billing/BalanceDisplay.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let role = '';
	export let help = false;
	export let className = 'max-w-[240px]';

	const dispatch = createEventDispatcher();

	let usage = null;

	const getUsageInfo = async () => {
		const res = await getUsage(localStorage.token).catch((error) => {
			console.error('Error fetching usage info:', error);
		});

		if (res) {
			usage = res;
		} else {
			usage = null;
		}
	};

	const loadBalance = async () => {
		try {
			const balanceInfo = await getBalance(localStorage.token);
			balance.set(balanceInfo);
		} catch (error) {
			console.error('Error fetching balance:', error);
		}
	};

	$: if (show) {
		getUsageInfo();
		loadBalance();
	}
</script>

<ShortcutsModal bind:show={$showShortcuts} />

<!-- svelte-ignore a11y-no-static-element-interactions -->
<DropdownMenu.Root
	bind:open={show}
	onOpenChange={(state) => {
		dispatch('change', state);
	}}
>
	<DropdownMenu.Trigger>
		<slot />
	</DropdownMenu.Trigger>

	<slot name="content">
		<DropdownMenu.Content
			class="w-full {className}  rounded-2xl px-1 py-1  border border-gray-100  dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg text-sm"
			sideOffset={4}
			side="bottom"
			align="start"
			transition={(e) => fade(e, { duration: 100 })}
		>
			<!-- 余额显示 -->
			<div class="px-2 py-2">
				<BalanceDisplay compact={true} />
			</div>

			<hr class="border-gray-50 dark:border-gray-800 my-1 p-0" />

			<!-- 计费中心入口 -->
			<DropdownMenu.Item
				as="a"
				href="/billing"
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition select-none"
				on:click={async () => {
					show = false;
					if ($mobile) {
						await tick();
						showSidebar.set(false);
					}
				}}
			>
				<div class="self-center mr-3">
					<svg
						class="w-5 h-5"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						xmlns="http://www.w3.org/2000/svg"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="1.5"
							d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				</div>
				<div class="self-center truncate">{$i18n.t('计费中心')}</div>
			</DropdownMenu.Item>

			<hr class="border-gray-50 dark:border-gray-800 my-1 p-0" />

			<DropdownMenu.Item
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer"
				on:click={async () => {
					show = false;

					await showSettings.set(true);

					if ($mobile) {
						await tick();
						showSidebar.set(false);
					}
				}}
			>
				<div class=" self-center mr-3">
					<Settings className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Settings')}</div>
			</DropdownMenu.Item>
			
			{#if false}
			<DropdownMenu.Item
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer"
				on:click={async () => {
					show = false;

					dispatch('show', 'archived-chat');

					if ($mobile) {
						await tick();

						showSidebar.set(false);
					}
				}}
			>
				<div class=" self-center mr-3">
					<ArchiveBox className="size-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Archived Chats')}</div>
			</DropdownMenu.Item>
			{/if}

			{#if role === 'admin'}
				<DropdownMenu.Item
					as="a"
					href="/playground"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition select-none"
					on:click={async () => {
						show = false;
						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<Code className="size-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Playground')}</div>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					as="a"
					href="/admin"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition select-none"
					on:click={async () => {
						show = false;
						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<UserGroup className="w-5 h-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('Admin Panel')}</div>
				</DropdownMenu.Item>
				<DropdownMenu.Item
					as="a"
					href="/announcements/manage"
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition select-none"
					on:click={async () => {
						show = false;
						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<UserGroup className="w-5 h-5" strokeWidth="1.5" />
					</div>
					<div class=" self-center truncate">{$i18n.t('公告管理')}</div>
				</DropdownMenu.Item>
			{:else}
				<DropdownMenu.Item
					class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer"
					on:click={async () => {
						show = false;
						dispatch('show', 'announcements');
						console.log('点击了公告');
						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<div class=" self-center mr-3">
						<!-- 公告图标 -->
						<svg
							class="w-5 h-5"
							viewBox="0 0 1024 1024"
							fill="currentColor"
							xmlns="http://www.w3.org/2000/svg"
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
					</div>
					<div class=" self-center truncate">{$i18n.t('公告')}</div>
				</DropdownMenu.Item>
			{/if}

			{#if help}
				<hr class=" border-gray-50 dark:border-gray-800 my-1 p-0" />

				<!-- {$i18n.t('Help')} -->

				{#if $user?.role === 'admin'}
					<DropdownMenu.Item
						as="a"
						target="_blank"
						class="flex gap-2 items-center py-1.5 px-3 text-sm select-none w-full cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition"
						id="chat-share-button"
						on:click={() => {
							show = false;
						}}
						href="https://docs.openwebui.com"
					>
						<QuestionMarkCircle className="size-5" />
						<div class="flex items-center">{$i18n.t('Documentation')}</div>
					</DropdownMenu.Item>

					<!-- Releases -->
					<DropdownMenu.Item
						as="a"
						target="_blank"
						class="flex gap-2 items-center py-1.5 px-3 text-sm select-none w-full cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition"
						id="chat-share-button"
						on:click={() => {
							show = false;
						}}
						href="https://github.com/open-webui/open-webui/releases"
					>
						<Map className="size-5" />
						<div class="flex items-center">{$i18n.t('Releases')}</div>
					</DropdownMenu.Item>
				{/if}

				<DropdownMenu.Item
					class="flex gap-2 items-center py-1.5 px-3 text-sm select-none w-full  hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition cursor-pointer"
					id="chat-share-button"
					on:click={async () => {
						show = false;
						showShortcuts.set(!$showShortcuts);

						if ($mobile) {
							await tick();
							showSidebar.set(false);
						}
					}}
				>
					<Keyboard className="size-5" />
					<div class="flex items-center">{$i18n.t('Keyboard shortcuts')}</div>
				</DropdownMenu.Item>
			{/if}

			<a
				href="/feedback"
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition cursor-pointer"
				on:click={async () => {
					show = false;
					if ($mobile) {
						await tick();
						showSidebar.set(false);
					}
				}}
			>
				<div class=" self-center mr-3">
					<!-- 反馈图标 -->
					<svg
						class="w-5 h-5"
						viewBox="0 0 1024 1024"
						fill="currentColor"
						xmlns="http://www.w3.org/2000/svg"
					>
						<path
							d="M931.302 94.293L960 122.99v360.313l-28.698 28.698H822.89L714.477 623.602l-51.018-22.32v-89.281h-63.772l3.189-28.698-3.189-31.886h121.167v76.527l76.527-76.527h105.224v-299.73H363.73v63.772l-31.886-3.189-28.698 3.189v-92.47l28.698-28.698h599.458v0.002zM446.633 658.677c29.76 12.754 56.332 30.823 79.715 54.206 23.383 23.383 41.452 52.081 54.206 86.093 10.629 23.383 17.006 46.766 19.132 70.149l3.189 60.584h-60.584v-31.886c0-27.635-5.314-53.675-15.943-78.121-10.629-24.446-25.509-46.766-44.641-66.961-19.132-20.195-41.452-35.606-66.961-46.235-25.509-10.629-52.081-15.943-79.715-15.943h-3.189c-27.635 0-54.206 5.314-79.715 15.943s-47.829 26.04-66.961 46.235c-19.132 20.195-34.012 42.515-44.641 66.961-10.629 24.446-15.943 50.486-15.943 78.121v31.886H64l3.189-57.395c2.126-25.509 7.44-49.955 15.943-73.338 14.88-34.012 34.012-62.709 57.395-86.093s48.892-41.452 76.527-54.206c-27.635-19.132-49.955-44.109-66.961-74.932s-25.509-64.835-25.509-102.036 9.034-71.744 27.103-103.63 43.578-57.395 76.527-76.527 68.024-28.698 105.224-28.698 71.744 9.566 103.63 28.698 57.395 44.641 76.527 76.527 28.698 66.429 28.698 103.63-8.503 71.212-25.509 102.036c-17.007 30.823-40.39 55.8-70.151 74.932z m-114.79-28.697c42.515 0 78.121-14.349 106.819-43.046s43.046-63.772 43.046-105.224-14.349-76.527-43.046-105.224-63.772-43.046-105.224-43.046-76.527 14.349-105.224 43.046c-28.697 28.698-43.046 63.772-43.046 105.224s14.349 76.527 43.046 105.224 63.24 43.046 103.629 43.046z"
						/>
					</svg>
				</div>
				<div class=" self-center truncate">{$i18n.t('反馈')}</div>
			</a>

			<hr class=" border-gray-50 dark:border-gray-800 my-1 p-0" />

			<DropdownMenu.Item
				class="flex rounded-xl py-1.5 px-3 w-full hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={async () => {
						const res = await userSignOut();
						logOutTracking();
						user.set(null);
						localStorage.removeItem('token');

					location.href = res?.redirect_url ?? '/auth';
					show = false;
				}}
			>
				<div class=" self-center mr-3">
					<SignOut className="w-5 h-5" strokeWidth="1.5" />
				</div>
				<div class=" self-center truncate">{$i18n.t('Sign Out')}</div>
			</DropdownMenu.Item>

			{#if usage && $user?.role === 'admin'}
				{#if usage?.user_ids?.length > 0}
					<hr class=" border-gray-50 dark:border-gray-800 my-1 p-0" />

					<Tooltip
						content={usage?.model_ids && usage?.model_ids.length > 0
							? `${$i18n.t('Running')}: ${usage.model_ids.join(', ')} ✨`
							: ''}
					>
						<div
							class="flex rounded-xl py-1 px-3 text-xs gap-2.5 items-center"
							on:mouseenter={() => {
								getUsageInfo();
							}}
						>
							<div class=" flex items-center">
								<span class="relative flex size-2">
									<span
										class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"
									/>
									<span class="relative inline-flex rounded-full size-2 bg-green-500" />
								</span>
							</div>

							<div class=" ">
								<span class="">
									{$i18n.t('Active Users')}:
								</span>
								<span class=" font-semibold">
									{usage?.user_ids?.length}
								</span>
							</div>
						</div>
					</Tooltip>
				{/if}
			{/if}

			<!-- <DropdownMenu.Item class="flex items-center py-1.5 px-3 text-sm ">
				<div class="flex items-center">Profile</div>
			</DropdownMenu.Item> -->
		</DropdownMenu.Content>
	</slot>
</DropdownMenu.Root>

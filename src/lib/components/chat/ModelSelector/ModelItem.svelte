<script lang="ts">
	import { marked } from 'marked';

import { getContext, tick } from 'svelte';
import dayjs from '$lib/dayjs';

import { mobile, settings, user, modelPricings } from '$lib/stores';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { copyToClipboard, sanitizeResponseContent } from '$lib/utils';
	import ArrowUpTray from '$lib/components/icons/ArrowUpTray.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import ModelItemMenu from './ModelItemMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import { toast } from 'svelte-sonner';
	import Tag from '$lib/components/icons/Tag.svelte';
	import Label from '$lib/components/icons/Label.svelte';
	import { createEventDispatcher } from 'svelte';

	const i18n = getContext('i18n');

	export let selectedModelIdx: number = -1;
	export let item: any = {};
	export let index: number = -1;
	export let value: string = '';

	export let unloadModelHandler: (modelValue: string) => void = () => {};
	export let pinModelHandler: (modelId: string) => void = () => {};

	export let onClick: () => void = () => {};

	const dispatch = createEventDispatcher();

	const copyLinkHandler = async (model) => {
		const baseUrl = window.location.origin;
		const res = await copyToClipboard(`${baseUrl}/?model=${encodeURIComponent(model.id)}`);

		if (res) {
			toast.success($i18n.t('Copied link to clipboard'));
		} else {
			toast.error($i18n.t('Failed to copy link'));
		}
	};

	let showMenu = false;

	// 响应式计算价格信息
	// 私有模型（source === 'user'）不显示价格
	$: pricing = (() => {
		// 私有模型不显示价格（用户自己的 API）
		if (item?.source === 'user') {
			return null;
		}

		return item?.model?.pricing ??
			item?.model?.info?.pricing ??
			$modelPricings?.[item?.model?.id ?? item?.value] ??
			null;
	})();

	const formatPrice = (price) => {
		if (price === undefined || price === null) return null;
		// 价格存储为毫/1k tokens（1 元 = 10000 毫）
		return (price / 10000).toFixed(2);
	};

	// 响应式判断第2行是否有内容需要显示
	// 私有模型（source === 'user'）始终保持单行，不显示第2行
	$: hasSecondLineContent = (() => {
		// 私有模型强制单行显示
		if (item?.source === 'user') {
			return false;
		}

		return (
			pricing || // 有价格
			(item.model.owned_by === 'ollama' && (item.model.ollama?.details?.parameter_size ?? '') !== '') || // Ollama 参数
			(item.model.owned_by === 'ollama' && item.model.ollama?.expires_at && new Date(item.model.ollama?.expires_at * 1000) > new Date()) || // Ollama 加载状态
			(item?.model?.tags ?? []).length > 0 || // Tags
			item.model?.direct || // Direct 标识
			item.model.connection_type === 'external' || // External 标识
			item.model?.info?.meta?.description // Description
		);
	})();
</script>

<button
	aria-roledescription="model-item"
	aria-label={item.label}
	class="flex group/item w-full text-left font-medium line-clamp-1 select-none items-center rounded-button py-2 pl-3 pr-1.5 text-sm text-gray-700 dark:text-gray-100 outline-hidden transition-all duration-75 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl cursor-pointer data-highlighted:bg-muted {index ===
	selectedModelIdx
		? 'bg-gray-100 dark:bg-gray-800 group-hover:bg-transparent'
		: ''}"
	data-arrow-selected={index === selectedModelIdx}
	data-value={item.value}
	on:click={() => {
		onClick();
	}}
>
	<div class="flex flex-col flex-1 gap-1.5">
		<!-- {#if (item?.model?.tags ?? []).length > 0}
			<div
				class="flex gap-0.5 self-center items-start h-full w-full translate-y-[0.5px] overflow-x-auto scrollbar-none"
			>
				{#each item.model?.tags.sort((a, b) => a.name.localeCompare(b.name)) as tag}
					<Tooltip content={tag.name} className="flex-shrink-0">
						<div
							class=" text-xs font-semibold px-1 rounded-sm uppercase bg-gray-500/20 text-gray-700 dark:text-gray-200"
						>
							{tag.name}
						</div>
					</Tooltip>
				{/each}
			</div>
		{/if} -->

		<!-- 第1行: 头像 + 名称 + My API 标签 -->
		<div class="flex items-center gap-2">
			<div class="flex items-center min-w-fit">
				<Tooltip content={$user?.role === 'admin' ? (item?.value ?? '') : ''} placement="top-start">
					<img
						src={item.model?.info?.meta?.profile_image_url ??
							`${WEBUI_BASE_URL}/static/favicon.png`}
						alt="Model"
						class="rounded-full size-5 flex items-center dark:invert"
					/>
				</Tooltip>
			</div>

			<div class="flex items-center gap-1.5 flex-1 min-w-0">
				<Tooltip content={`${item.label}`} placement="top-start">
					<div class="line-clamp-1 font-medium">
						{item.label}
					</div>
				</Tooltip>

				{#if item?.source === 'user'}
					<div
						class="inline-flex items-center rounded-full bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400 px-1.5 py-0.5 text-[10px] font-medium shrink-0"
					>
						{$i18n.t('My API')}
					</div>
				{/if}
			</div>
		</div>

		<!-- 第2行: 价格 + 参数大小 + 其他图标 -->
		{#if hasSecondLineContent}
		<div class="flex items-center gap-2 text-xs ml-7">
			<!-- 紧凑价格格式 -->
			{#if pricing}
				<span class="text-gray-600 dark:text-gray-400">
					{#if formatPrice(pricing.input_price)}
						<span class="text-gray-500 dark:text-gray-500">输入</span>
						<span class="font-mono">¥{formatPrice(pricing.input_price)}/M</span>
					{/if}
					{#if formatPrice(pricing.input_price) && formatPrice(pricing.output_price)}
						<span class="mx-1.5 text-gray-300 dark:text-gray-600">|</span>
					{/if}
					{#if formatPrice(pricing.output_price)}
						<span class="text-gray-500 dark:text-gray-500">输出</span>
						<span class="font-mono">¥{formatPrice(pricing.output_price)}/M</span>
					{/if}
				</span>
			{/if}


			<!-- Description 图标 -->
			{#if item.model?.info?.meta?.description}
				<Tooltip
					content={`${marked.parse(
						sanitizeResponseContent(item.model?.info?.meta?.description).replaceAll('\n', '<br>')
					)}`}
				>
					<div class="translate-y-[1px]">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="1.5"
							stroke="currentColor"
							class="w-4 h-4"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
							/>
						</svg>
					</div>
				</Tooltip>
			{/if}
		</div>
		{/if}
	</div>

	<div class="ml-auto pl-2 pr-1 flex items-center gap-1.5 shrink-0">
		{#if $user?.role === 'admin' && item.model.owned_by === 'ollama' && item.model.ollama?.expires_at && new Date(item.model.ollama?.expires_at * 1000) > new Date()}
			<Tooltip
				content={`${$i18n.t('Eject')}`}
				className="flex-shrink-0 group-hover/item:opacity-100 opacity-0 "
			>
				<button
					class="flex"
					on:click={(e) => {
						e.preventDefault();
						e.stopPropagation();
						unloadModelHandler(item.value);
					}}
				>
					<ArrowUpTray className="size-3" />
				</button>
			</Tooltip>
		{/if}

		<ModelItemMenu
			bind:show={showMenu}
			model={item.model}
			{item}
			{pinModelHandler}
			copyLinkHandler={() => {
				copyLinkHandler(item.model);
			}}
			onDelete={(cred) => {
				const target = cred?._credential ?? cred;
				dispatch('deleteUserModel', target);
			}}
		>
			<button
				aria-label={`${$i18n.t('More Options')}`}
				class="flex"
				on:click={(e) => {
					e.preventDefault();
					e.stopPropagation();
					showMenu = !showMenu;
				}}
			>
				<EllipsisHorizontal />
			</button>
		</ModelItemMenu>

		{#if value === item.value}
			<div>
				<Check className="size-3" />
			</div>
		{/if}
	</div>
</button>

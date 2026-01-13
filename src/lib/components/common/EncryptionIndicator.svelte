<script lang="ts">
	import { onMount } from 'svelte';

	export let show: boolean = false;
	export let variant: 'inline' | 'badge' = 'inline';

	let dots = '';
	let interval: NodeJS.Timeout;

	onMount(() => {
		// 动画效果：循环显示 . .. ...
		interval = setInterval(() => {
			if (dots.length >= 3) {
				dots = '';
			} else {
				dots += '.';
			}
		}, 500);

		return () => {
			if (interval) clearInterval(interval);
		};
	});
</script>

{#if show}
	{#if variant === 'inline'}
		<!-- 内联样式：跟随文本流 -->
		<span class="inline-flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 ml-2">
			<svg
				class="w-3.5 h-3.5 animate-spin"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
				/>
			</svg>
			<span class="font-medium">加密传输中{dots}</span>
		</span>
	{:else}
		<!-- 徽章样式：独立显示 -->
		<div
			class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
		>
			<div class="relative flex items-center justify-center">
				<!-- 脉冲动画圆圈 -->
				<span
					class="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 animate-ping"
				></span>
				<!-- 锁图标 -->
				<svg
					class="relative w-4 h-4 text-blue-600 dark:text-blue-400"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
					/>
				</svg>
			</div>
			<span class="text-sm font-medium text-blue-700 dark:text-blue-300">
				加密传输中{dots}
			</span>
		</div>
	{/if}
{/if}

<style>
	@keyframes ping {
		75%,
		100% {
			transform: scale(2);
			opacity: 0;
		}
	}

	.animate-ping {
		animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
	}

	.animate-spin {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}
</style>

<script lang="ts">
	import { onMount } from 'svelte';

	export let size = 'md';

	// 随机选择一种动画类型
	const animations = ['ecg', 'breathing', 'thinking', 'wave'] as const;
	let animationType: typeof animations[number] = 'ecg';

	onMount(() => {
		// 组件挂载时随机选择动画类型
		animationType = animations[Math.floor(Math.random() * animations.length)];
	});

	// 根据size计算容器高度
	const containerSize = size === 'md' ? 'h-6' : size === 'xs' ? 'h-3' : 'h-4';
</script>

<div class="inline-flex items-center {containerSize} mx-1 my-2">
	{#if animationType === 'ecg'}
		<!-- 心电图波形 -->
		<div class="flex items-center gap-0.5 h-full">
			<svg class="ecg-wave {size === 'md' ? 'w-16' : size === 'xs' ? 'w-8' : 'w-12'} h-full" viewBox="0 0 100 40" preserveAspectRatio="none">
				<polyline
					class="ecg-line stroke-blue-500 dark:stroke-blue-400"
					fill="none"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					points="0,20 20,20 25,5 30,35 35,20 100,20"
				/>
			</svg>
		</div>

	{:else if animationType === 'breathing'}
		<!-- 呼吸式光晕 -->
		<div class="relative {size === 'md' ? 'size-4' : size === 'xs' ? 'size-2' : 'size-3'}">
			<div class="absolute inset-0 breathing-glow rounded-full bg-gradient-to-r from-blue-400 to-purple-400 opacity-60"></div>
			<div class="absolute inset-0 breathing-core rounded-full bg-gradient-to-r from-blue-500 to-purple-500"></div>
		</div>

	{:else if animationType === 'thinking'}
		<!-- 思考气泡 -->
		<div class="flex items-center gap-1">
			<span class="thinking-dot thinking-dot-1 {size === 'md' ? 'size-2' : size === 'xs' ? 'size-1' : 'size-1.5'} rounded-full bg-gray-600 dark:bg-gray-300"></span>
			<span class="thinking-dot thinking-dot-2 {size === 'md' ? 'size-2' : size === 'xs' ? 'size-1' : 'size-1.5'} rounded-full bg-gray-600 dark:bg-gray-300"></span>
			<span class="thinking-dot thinking-dot-3 {size === 'md' ? 'size-2' : size === 'xs' ? 'size-1' : 'size-1.5'} rounded-full bg-gray-600 dark:bg-gray-300"></span>
		</div>

	{:else if animationType === 'wave'}
		<!-- 波浪律动 -->
		<div class="flex items-center gap-0.5 h-full">
			<span class="wave-bar wave-bar-1 {size === 'md' ? 'w-1' : size === 'xs' ? 'w-0.5' : 'w-0.5'} bg-gradient-to-t from-cyan-500 to-blue-500 rounded-full"></span>
			<span class="wave-bar wave-bar-2 {size === 'md' ? 'w-1' : size === 'xs' ? 'w-0.5' : 'w-0.5'} bg-gradient-to-t from-cyan-500 to-blue-500 rounded-full"></span>
			<span class="wave-bar wave-bar-3 {size === 'md' ? 'w-1' : size === 'xs' ? 'w-0.5' : 'w-0.5'} bg-gradient-to-t from-cyan-500 to-blue-500 rounded-full"></span>
			<span class="wave-bar wave-bar-4 {size === 'md' ? 'w-1' : size === 'xs' ? 'w-0.5' : 'w-0.5'} bg-gradient-to-t from-cyan-500 to-blue-500 rounded-full"></span>
			<span class="wave-bar wave-bar-5 {size === 'md' ? 'w-1' : size === 'xs' ? 'w-0.5' : 'w-0.5'} bg-gradient-to-t from-cyan-500 to-blue-500 rounded-full"></span>
		</div>
	{/if}
</div>

<style>
	/* 心电图动画 */
	@keyframes ecg {
		0% {
			stroke-dashoffset: 200;
		}
		100% {
			stroke-dashoffset: 0;
		}
	}

	.ecg-line {
		stroke-dasharray: 200;
		stroke-dashoffset: 200;
		animation: ecg 1.5s ease-in-out infinite;
	}

	.ecg-wave {
		filter: drop-shadow(0 0 2px currentColor);
	}

	/* 呼吸式动画 */
	@keyframes breathing-glow {
		0%, 100% {
			transform: scale(1);
			opacity: 0.3;
		}
		50% {
			transform: scale(1.8);
			opacity: 0.1;
		}
	}

	@keyframes breathing-core {
		0%, 100% {
			transform: scale(0.8);
			opacity: 0.9;
		}
		50% {
			transform: scale(1);
			opacity: 1;
		}
	}

	.breathing-glow {
		animation: breathing-glow 3s ease-in-out infinite;
	}

	.breathing-core {
		animation: breathing-core 3s ease-in-out infinite;
	}

	/* 思考气泡动画 */
	@keyframes thinking-bounce {
		0%, 60%, 100% {
			transform: translateY(0);
		}
		30% {
			transform: translateY(-8px);
		}
	}

	.thinking-dot {
		animation: thinking-bounce 1.4s ease-in-out infinite;
	}

	.thinking-dot-1 {
		animation-delay: 0s;
	}

	.thinking-dot-2 {
		animation-delay: 0.2s;
	}

	.thinking-dot-3 {
		animation-delay: 0.4s;
	}

	/* 波浪律动动画 */
	@keyframes wave-height {
		0%, 100% {
			height: 20%;
		}
		50% {
			height: 100%;
		}
	}

	.wave-bar {
		animation: wave-height 1.2s ease-in-out infinite;
	}

	.wave-bar-1 {
		animation-delay: 0s;
	}

	.wave-bar-2 {
		animation-delay: 0.1s;
	}

	.wave-bar-3 {
		animation-delay: 0.2s;
	}

	.wave-bar-4 {
		animation-delay: 0.3s;
	}

	.wave-bar-5 {
		animation-delay: 0.4s;
	}
</style>

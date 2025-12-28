<script lang="ts">
	import { onMount } from 'svelte';

	export let size = 'md';

	// 随机选择一种动画类型
	const animations = ['ecg', 'thinking', 'wave'] as const;
	let animationType: typeof animations[number] | 'dog' = 'ecg';

	onMount(() => {
		// 10% 概率出现小狗彩蛋
		const random = Math.random();
		if (random < 0.1) {
			animationType = 'dog';
		} else {
			// 其余90%从常规动画中随机选择
			animationType = animations[Math.floor(Math.random() * animations.length)];
		}
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

	{:else if animationType === 'dog'}
		<!-- 🐕 欢快的小狗彩蛋 -->
		<div class="dog-container {size === 'md' ? 'scale-100' : size === 'xs' ? 'scale-75' : 'scale-90'}">
			<div class="dog">
				<!-- 身体 -->
				<div class="dog-body"></div>
				<!-- 头部 -->
				<div class="dog-head">
					<!-- 耳朵 -->
					<div class="dog-ear dog-ear-left"></div>
					<div class="dog-ear dog-ear-right"></div>
					<!-- 眼睛 -->
					<div class="dog-eyes">
						<div class="dog-eye"></div>
						<div class="dog-eye"></div>
					</div>
					<!-- 鼻子 -->
					<div class="dog-nose"></div>
				</div>
				<!-- 尾巴 -->
				<div class="dog-tail"></div>
				<!-- 腿 -->
				<div class="dog-legs">
					<div class="dog-leg dog-leg-1"></div>
					<div class="dog-leg dog-leg-2"></div>
				</div>
			</div>
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

	/* 小狗彩蛋动画 */
	.dog-container {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 24px;
		width: 32px;
		transform-origin: center;
	}

	.dog {
		position: relative;
		animation: dog-jump 0.6s ease-in-out infinite;
	}

	@keyframes dog-jump {
		0%, 100% {
			transform: translateY(0) rotate(0deg);
		}
		50% {
			transform: translateY(-4px) rotate(2deg);
		}
	}

	.dog-body {
		width: 14px;
		height: 10px;
		background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
		border-radius: 6px 6px 4px 4px;
		position: relative;
	}

	.dog-head {
		position: absolute;
		top: -6px;
		left: 9px;
		width: 10px;
		height: 10px;
		background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
		border-radius: 5px;
		z-index: 2;
	}

	.dog-ear {
		position: absolute;
		width: 4px;
		height: 5px;
		background: #d97706;
		border-radius: 3px 3px 0 0;
		animation: ear-wiggle 0.8s ease-in-out infinite;
	}

	.dog-ear-left {
		left: 0;
		top: -2px;
		transform-origin: bottom center;
	}

	.dog-ear-right {
		right: 0;
		top: -2px;
		transform-origin: bottom center;
		animation-delay: 0.1s;
	}

	@keyframes ear-wiggle {
		0%, 100% {
			transform: rotate(-10deg);
		}
		50% {
			transform: rotate(10deg);
		}
	}

	.dog-eyes {
		position: absolute;
		top: 3px;
		left: 2px;
		display: flex;
		gap: 3px;
	}

	.dog-eye {
		width: 2px;
		height: 2px;
		background: #1f2937;
		border-radius: 50%;
		animation: blink 2s ease-in-out infinite;
	}

	@keyframes blink {
		0%, 48%, 52%, 100% {
			transform: scaleY(1);
		}
		50% {
			transform: scaleY(0.1);
		}
	}

	.dog-nose {
		position: absolute;
		bottom: 2px;
		left: 50%;
		transform: translateX(-50%);
		width: 2px;
		height: 2px;
		background: #1f2937;
		border-radius: 50%;
	}

	.dog-tail {
		position: absolute;
		right: -3px;
		top: 1px;
		width: 6px;
		height: 2px;
		background: #f59e0b;
		border-radius: 0 2px 2px 0;
		transform-origin: left center;
		animation: tail-wag 0.3s ease-in-out infinite;
	}

	@keyframes tail-wag {
		0%, 100% {
			transform: rotate(-20deg);
		}
		50% {
			transform: rotate(20deg);
		}
	}

	.dog-legs {
		position: absolute;
		bottom: -4px;
		left: 2px;
		display: flex;
		gap: 6px;
	}

	.dog-leg {
		width: 2px;
		height: 4px;
		background: #d97706;
		border-radius: 0 0 1px 1px;
		animation: leg-walk 0.4s ease-in-out infinite;
	}

	.dog-leg-1 {
		animation-delay: 0s;
	}

	.dog-leg-2 {
		animation-delay: 0.2s;
	}

	@keyframes leg-walk {
		0%, 100% {
			transform: scaleY(1);
		}
		50% {
			transform: scaleY(0.8);
		}
	}
</style>

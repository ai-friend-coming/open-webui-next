<script lang="ts">
	import { onMount } from 'svelte';

	export let size = 'md';

	// 随机选择一种动画类型
	const animations = ['ecg', 'thinking', 'wave'] as const;
	let animationType: typeof animations[number] | 'dog' | 'bear' = 'ecg';

	onMount(() => {
		// 10% 概率出现小狗彩蛋，10% 概率出现北极熊彩蛋
		const random = Math.random();
		if (random < 0.1) {
			animationType = 'dog';
		} else if (random < 0.2) {
			animationType = 'bear';
		} else {
			// 其余80%从常规动画中随机选择
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

	{:else if animationType === 'bear'}
		<!-- 🐻‍❄️ 可爱的北极熊彩蛋 -->
		<div class="bear-container {size === 'md' ? 'scale-100' : size === 'xs' ? 'scale-75' : 'scale-90'}">
			<div class="bear">
				<!-- 身体 -->
				<div class="bear-body"></div>
				<!-- 头部 -->
				<div class="bear-head">
					<!-- 耳朵 -->
					<div class="bear-ear bear-ear-left"></div>
					<div class="bear-ear bear-ear-right"></div>
					<!-- 眼睛 -->
					<div class="bear-eyes">
						<div class="bear-eye"></div>
						<div class="bear-eye"></div>
					</div>
					<!-- 鼻子 -->
					<div class="bear-nose"></div>
					<!-- 嘴巴 -->
					<div class="bear-mouth"></div>
				</div>
				<!-- 前爪 -->
				<div class="bear-paws">
					<div class="bear-paw bear-paw-left"></div>
					<div class="bear-paw bear-paw-right"></div>
				</div>
				<!-- 后腿 -->
				<div class="bear-legs">
					<div class="bear-leg bear-leg-1"></div>
					<div class="bear-leg bear-leg-2"></div>
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

	/* 北极熊彩蛋动画 */
	.bear-container {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: 26px;
		width: 36px;
		transform-origin: center;
	}

	.bear {
		position: relative;
		animation: bear-waddle 1s ease-in-out infinite;
	}

	@keyframes bear-waddle {
		0%, 100% {
			transform: translateY(0) rotate(-2deg);
		}
		50% {
			transform: translateY(-2px) rotate(2deg);
		}
	}

	.bear-body {
		width: 18px;
		height: 14px;
		background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #bae6fd 100%);
		border-radius: 8px 8px 6px 6px;
		position: relative;
		box-shadow: 0 2px 4px rgba(147, 197, 253, 0.3);
	}

	.bear-head {
		position: absolute;
		top: -8px;
		left: 10px;
		width: 12px;
		height: 12px;
		background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 50%, #bae6fd 100%);
		border-radius: 6px;
		z-index: 2;
		box-shadow: 0 2px 3px rgba(147, 197, 253, 0.2);
	}

	.bear-ear {
		position: absolute;
		width: 4px;
		height: 4px;
		background: #bae6fd;
		border-radius: 50%;
		animation: bear-ear-twitch 1.5s ease-in-out infinite;
	}

	.bear-ear-left {
		left: 1px;
		top: -1px;
	}

	.bear-ear-right {
		right: 1px;
		top: -1px;
		animation-delay: 0.2s;
	}

	@keyframes bear-ear-twitch {
		0%, 90%, 100% {
			transform: scale(1);
		}
		95% {
			transform: scale(1.15);
		}
	}

	.bear-eyes {
		position: absolute;
		top: 4px;
		left: 2px;
		display: flex;
		gap: 4px;
	}

	.bear-eye {
		width: 2px;
		height: 2px;
		background: #1e293b;
		border-radius: 50%;
		animation: bear-blink 3s ease-in-out infinite;
	}

	@keyframes bear-blink {
		0%, 46%, 50%, 100% {
			transform: scaleY(1);
		}
		48% {
			transform: scaleY(0.1);
		}
	}

	.bear-nose {
		position: absolute;
		bottom: 3px;
		left: 50%;
		transform: translateX(-50%);
		width: 2.5px;
		height: 2px;
		background: #1e293b;
		border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
	}

	.bear-mouth {
		position: absolute;
		bottom: 1px;
		left: 50%;
		transform: translateX(-50%);
		width: 4px;
		height: 2px;
		border: 0.5px solid #64748b;
		border-top: none;
		border-radius: 0 0 50% 50%;
	}

	.bear-paws {
		position: absolute;
		top: 6px;
		left: 0;
		display: flex;
		gap: 12px;
		z-index: 1;
	}

	.bear-paw {
		width: 4px;
		height: 5px;
		background: linear-gradient(180deg, #e0f2fe 0%, #bae6fd 100%);
		border-radius: 2px 2px 2.5px 2.5px;
		box-shadow: 0 1px 2px rgba(147, 197, 253, 0.3);
	}

	.bear-paw-left {
		animation: bear-wave-left 1.2s ease-in-out infinite;
		transform-origin: top center;
	}

	.bear-paw-right {
		animation: bear-wave-right 1.2s ease-in-out infinite;
		transform-origin: top center;
	}

	@keyframes bear-wave-left {
		0%, 100% {
			transform: rotate(-15deg);
		}
		50% {
			transform: rotate(10deg);
		}
	}

	@keyframes bear-wave-right {
		0%, 100% {
			transform: rotate(15deg);
		}
		50% {
			transform: rotate(-10deg);
		}
	}

	.bear-legs {
		position: absolute;
		bottom: -5px;
		left: 4px;
		display: flex;
		gap: 8px;
	}

	.bear-leg {
		width: 3px;
		height: 5px;
		background: linear-gradient(180deg, #e0f2fe 0%, #bae6fd 100%);
		border-radius: 0 0 1.5px 1.5px;
		box-shadow: 0 1px 2px rgba(147, 197, 253, 0.2);
		animation: bear-step 0.8s ease-in-out infinite;
	}

	.bear-leg-1 {
		animation-delay: 0s;
	}

	.bear-leg-2 {
		animation-delay: 0.4s;
	}

	@keyframes bear-step {
		0%, 100% {
			transform: scaleY(1) translateY(0);
		}
		50% {
			transform: scaleY(0.85) translateY(1px);
		}
	}
</style>

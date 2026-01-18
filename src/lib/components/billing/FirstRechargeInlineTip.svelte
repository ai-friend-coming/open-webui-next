<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { slide } from 'svelte/transition';
	import { getFirstRechargeBonusConfig, checkFirstRechargeBonusEligibility } from '$lib/apis/first-recharge-bonus';

	export let messageCount = 0; // 用户发送的消息数量
	export let showAfterMessages = 5; // 发送多少条消息后显示提示

	let showTip = false;
	let dismissed = false;
	let bonusConfig: any = null;

	onMount(async () => {
		try {
			const [config, eligibility] = await Promise.all([
				getFirstRechargeBonusConfig(localStorage.token),
				checkFirstRechargeBonusEligibility(localStorage.token)
			]);

			if (eligibility?.eligible && config?.enabled) {
				bonusConfig = config;
				// 检查是否已经关闭过
				const dismissed = localStorage.getItem('firstRechargeTipDismissed');
				if (!dismissed && messageCount >= showAfterMessages) {
					showTip = true;
				}
			}
		} catch (error) {
			console.error('Failed to check first recharge eligibility:', error);
		}
	});

	$: if (messageCount >= showAfterMessages && bonusConfig && !dismissed) {
		const wasDismissed = localStorage.getItem('firstRechargeTipDismissed');
		if (!wasDismissed) {
			showTip = true;
		}
	}

	const handleRecharge = () => {
		goto('/billing');
	};

	const handleDismiss = () => {
		dismissed = true;
		showTip = false;
		localStorage.setItem('firstRechargeTipDismissed', 'true');
	};

	$: bonusRate = bonusConfig?.bonus_rate ? (bonusConfig.bonus_rate * 100).toFixed(0) : '0';
</script>

{#if showTip && !dismissed}
	<div
		class="chat-tip"
		transition:slide
	>
		<div class="tip-content">
			<div class="tip-icon">💡</div>
			<div class="tip-text">
				<span class="tip-label">提示：</span>
				首次充值可享 <strong>{bonusRate}%</strong> 奖励，最高送 <strong>¥{(bonusConfig?.max_bonus_amount / 10000).toFixed(0)}</strong> 元
			</div>
			<button class="tip-action" on:click={handleRecharge}>
				去充值
			</button>
			<button class="tip-close" on:click={handleDismiss}>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
	</div>
{/if}

<style>
	.chat-tip {
		position: fixed;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		z-index: 40;
		max-width: 90%;
		width: auto;
	}

	.tip-content {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: linear-gradient(135deg, rgba(251, 191, 36, 0.95) 0%, rgba(245, 158, 11, 0.95) 100%);
		backdrop-filter: blur(12px);
		border-radius: 9999px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.1);
		color: white;
		font-size: 0.875rem;
		animation: slide-up 0.3s ease-out;
	}

	@media (max-width: 640px) {
		.tip-content {
			flex-wrap: wrap;
			border-radius: 1rem;
			padding: 0.875rem 1rem;
		}
	}

	.tip-icon {
		font-size: 1.25rem;
		flex-shrink: 0;
	}

	.tip-text {
		flex: 1;
		line-height: 1.4;
		min-width: 0;
	}

	.tip-label {
		font-weight: 600;
		margin-right: 0.25rem;
	}

	.tip-text strong {
		font-weight: 700;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
	}

	.tip-action {
		padding: 0.375rem 0.875rem;
		background: white;
		color: #f59e0b;
		border: none;
		border-radius: 9999px;
		font-weight: 600;
		font-size: 0.875rem;
		cursor: pointer;
		transition: all 0.2s;
		flex-shrink: 0;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
	}

	.tip-action:hover {
		transform: scale(1.05);
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
	}

	.tip-action:active {
		transform: scale(0.98);
	}

	.tip-close {
		padding: 0.25rem;
		background: rgba(255, 255, 255, 0.2);
		border: none;
		border-radius: 50%;
		color: white;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
		flex-shrink: 0;
	}

	.tip-close:hover {
		background: rgba(255, 255, 255, 0.3);
	}

	@keyframes slide-up {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(1rem);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}
</style>

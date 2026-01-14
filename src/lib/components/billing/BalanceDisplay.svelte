<script lang="ts">
	import { balance, isLowBalance, isFrozen, formatCurrency } from '$lib/stores';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let compact = false; // 紧凑模式（用于侧边栏）
</script>

{#if $balance}
	<div class="balance-display" class:compact>
		<div class="balance-info">
			<div class="balance-label text-xs opacity-80">{$i18n.t('当前余额')}</div>
			<div
				class="balance-amount font-bold mt-1"
				class:low={$isLowBalance}
				class:frozen={$isFrozen}
			>
				{formatCurrency($balance.balance)}
			</div>
		</div>

		{#if !compact}
			<div class="consumed-info mt-3 pt-3 border-t border-white/20">
				<div class="consumed-label text-xs opacity-80">{$i18n.t('累计消费')}</div>
				<div class="consumed-amount text-sm font-semibold mt-1">
					{formatCurrency($balance.total_consumed)}
				</div>
			</div>
		{/if}

		{#if $isFrozen}
			<div class="status-badge frozen mt-2">
				{$i18n.t('账户已冻结')}
			</div>
		{:else if $isLowBalance}
			<div class="status-badge warning mt-2">
				{$i18n.t('余额不足')}
			</div>
		{/if}
	</div>
{/if}

<style>
	.balance-display {
		padding: 1.5rem;
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.7);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1px solid rgba(255, 255, 255, 0.3);
		box-shadow: 0 8px 32px 0 rgba(99, 102, 241, 0.15);
		position: relative;
		overflow: hidden;
	}

	.balance-display::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 4px;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
	}

	:global(.dark) .balance-display {
		background: rgba(31, 41, 55, 0.7);
		border: 1px solid rgba(255, 255, 255, 0.1);
		box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
	}

	.balance-display.compact {
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
	}

	.balance-label {
		color: #6b7280;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	:global(.dark) .balance-label {
		color: #9ca3af;
	}

	.balance-amount {
		font-size: 2.25rem;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
		font-weight: 800;
		letter-spacing: -0.02em;
	}

	.balance-display.compact .balance-amount {
		font-size: 1.5rem;
	}

	.balance-amount.low {
		background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.balance-amount.frozen {
		background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
		-webkit-background-clip: text;
		-webkit-text-fill-color: transparent;
		background-clip: text;
	}

	.consumed-info {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid rgba(107, 114, 128, 0.2);
	}

	:global(.dark) .consumed-info {
		border-top-color: rgba(156, 163, 175, 0.2);
	}

	.consumed-label {
		color: #6b7280;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	:global(.dark) .consumed-label {
		color: #9ca3af;
	}

	.consumed-amount {
		color: #374151;
		font-weight: 600;
	}

	:global(.dark) .consumed-amount {
		color: #d1d5db;
	}

	.status-badge {
		padding: 0.375rem 0.75rem;
		border-radius: 0.5rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-align: center;
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
	}

	.status-badge.warning {
		background: rgba(251, 191, 36, 0.2);
		color: #f59e0b;
		border: 1px solid rgba(251, 191, 36, 0.3);
	}

	:global(.dark) .status-badge.warning {
		background: rgba(251, 191, 36, 0.15);
		color: #fbbf24;
	}

	.status-badge.frozen {
		background: rgba(239, 68, 68, 0.2);
		color: #ef4444;
		border: 1px solid rgba(239, 68, 68, 0.3);
	}

	:global(.dark) .status-badge.frozen {
		background: rgba(239, 68, 68, 0.15);
		color: #f87171;
	}
</style>

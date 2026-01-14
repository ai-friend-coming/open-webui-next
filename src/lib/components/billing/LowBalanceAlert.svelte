<script lang="ts">
	import { isLowBalance, isFrozen, balance, formatCurrency } from '$lib/stores';
	import { getContext } from 'svelte';
	import { slide } from 'svelte/transition';

	const i18n = getContext('i18n');

	let dismissed = false;

	const dismiss = () => {
		dismissed = true;
	};
</script>

{#if ($isLowBalance || $isFrozen) && !dismissed}
	<div class="alert backdrop-blur-xl rounded-xl border shadow-lg" class:frozen={$isFrozen} transition:slide>
		<div class="alert-icon">
			{#if $isFrozen}
				<div class="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
					<svg class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
				</div>
			{:else}
				<div class="p-2 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
					<svg class="w-5 h-5 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
					</svg>
				</div>
			{/if}
		</div>
		<div class="alert-content">
			<div class="alert-title">
				{#if $isFrozen}
					{$i18n.t('账户已冻结')}
				{:else}
					{$i18n.t('余额不足')}
				{/if}
			</div>
			<div class="alert-message">
				{#if $isFrozen}
					{$i18n.t('您的账户余额不足，已被冻结。请联系管理员充值。')}
				{:else}
					{$i18n.t('当前余额')}: {formatCurrency($balance?.balance || 0)}，{$i18n.t(
						'请及时充值以免影响使用。'
					)}
				{/if}
			</div>
		</div>
		<button class="alert-close" on:click={dismiss}>
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
			</svg>
		</button>
	</div>
{/if}

<style>
	.alert {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 1rem 1.25rem;
		background: rgba(254, 243, 199, 0.9);
		border-color: rgba(251, 191, 36, 0.3);
		margin-bottom: 1.5rem;
	}

	.alert.frozen {
		background: rgba(254, 226, 226, 0.9);
		border-color: rgba(239, 68, 68, 0.3);
	}

	:global(.dark) .alert {
		background: rgba(120, 53, 15, 0.3);
		border-color: rgba(251, 191, 36, 0.2);
	}

	:global(.dark) .alert.frozen {
		background: rgba(127, 29, 29, 0.3);
		border-color: rgba(239, 68, 68, 0.2);
	}

	.alert-icon {
		flex-shrink: 0;
	}

	.alert-content {
		flex: 1;
	}

	.alert-title {
		font-weight: 700;
		margin-bottom: 0.25rem;
		color: #78350f;
		font-size: 0.95rem;
	}

	.alert.frozen .alert-title {
		color: #7f1d1d;
	}

	:global(.dark) .alert-title {
		color: #fbbf24;
	}

	:global(.dark) .alert.frozen .alert-title {
		color: #f87171;
	}

	.alert-message {
		font-size: 0.875rem;
		color: #78350f;
		line-height: 1.5;
	}

	.alert.frozen .alert-message {
		color: #7f1d1d;
	}

	:global(.dark) .alert-message {
		color: #fde68a;
	}

	:global(.dark) .alert.frozen .alert-message {
		color: #fecaca;
	}

	.alert-close {
		color: #78350f;
		cursor: pointer;
		background: none;
		border: none;
		padding: 0.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border-radius: 0.5rem;
		transition: all 0.2s;
	}

	.alert-close:hover {
		background: rgba(0, 0, 0, 0.1);
		color: #451a03;
	}

	:global(.dark) .alert-close {
		color: #fbbf24;
	}

	:global(.dark) .alert-close:hover {
		background: rgba(255, 255, 255, 0.1);
		color: #fde68a;
	}
</style>

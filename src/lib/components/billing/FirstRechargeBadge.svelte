<script lang="ts">
	import { onMount } from 'svelte';
	import { getFirstRechargeBonusConfig, checkFirstRechargeBonusEligibility } from '$lib/apis/billing';

	let showBadge = false;

	onMount(async () => {
		try {
			const [config, eligibility] = await Promise.all([
				getFirstRechargeBonusConfig(),
				checkFirstRechargeBonusEligibility(localStorage.token)
			]);
			showBadge = eligibility?.eligible && config?.enabled;
		} catch (error) {
			console.error('Failed to check first recharge eligibility:', error);
		}
	});
</script>

{#if showBadge}
	<span class="first-recharge-badge">
		<span class="badge-dot"></span>
		<span class="badge-text">NEW</span>
	</span>
{/if}

<style>
	.first-recharge-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.125rem 0.5rem;
		background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
		color: white;
		border-radius: 9999px;
		font-size: 0.625rem;
		font-weight: 700;
		letter-spacing: 0.025em;
		box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
		animation: badge-pulse 2s ease-in-out infinite;
	}

	.badge-dot {
		width: 0.375rem;
		height: 0.375rem;
		background: white;
		border-radius: 50%;
		animation: dot-pulse 1.5s ease-in-out infinite;
	}

	.badge-text {
		line-height: 1;
	}

	@keyframes badge-pulse {
		0%, 100% {
			transform: scale(1);
			opacity: 1;
		}
		50% {
			transform: scale(1.05);
			opacity: 0.95;
		}
	}

	@keyframes dot-pulse {
		0%, 100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}
</style>

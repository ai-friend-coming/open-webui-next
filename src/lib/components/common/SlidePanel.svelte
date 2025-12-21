<script lang="ts">
	import { onDestroy } from 'svelte';
	import { fly, fade } from 'svelte/transition';

	export let show = false;
	export let className = '';
	export let onClose = () => {};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			show = false;
		}
	};

	const handleClose = () => {
		show = false;
		onClose();
	};

	$: if (show) {
		window.addEventListener('keydown', handleKeyDown);
		document.body.style.overflow = 'hidden';
	} else {
		window.removeEventListener('keydown', handleKeyDown);
		document.body.style.overflow = '';
	}

	onDestroy(() => {
		window.removeEventListener('keydown', handleKeyDown);
		document.body.style.overflow = '';
	});
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->

{#if show}
	<div
		class="slide-panel fixed inset-0 bg-black/60 w-full h-screen max-h-[100dvh] flex z-[999] overflow-hidden overscroll-contain"
		transition:fade={{ duration: 200 }}
		on:mousedown={handleClose}
	>
		<div
			class="h-full w-[280px] max-w-[85vw] bg-gray-50 dark:bg-gray-900 dark:text-gray-100 {className} overflow-y-auto scrollbar-hidden"
			transition:fly={{ x: -280, duration: 200 }}
			on:mousedown|stopPropagation
		>
			<slot />
		</div>
	</div>
{/if}

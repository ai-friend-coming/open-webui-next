<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import Modal from '$lib/components/common/Modal.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	export let show = false;
	export let config = {
		GLOBAL_API_KEY: '',
		GLOBAL_API_BASE_URL: '',
		GLOBAL_API_MODEL_ID: ''
	};
	export let onSubmit: Function = () => {};

	let apiKey = '';
	let baseUrl = '';
	let modelId = '';
	let initialized = false;

	$: if (show && !initialized) {
		apiKey = config.GLOBAL_API_KEY;
		baseUrl = config.GLOBAL_API_BASE_URL;
		modelId = config.GLOBAL_API_MODEL_ID;
		initialized = true;
	}

	$: if (!show) {
		initialized = false;
	}

	const submitHandler = async () => {
		await onSubmit({
			GLOBAL_API_KEY: apiKey,
			GLOBAL_API_BASE_URL: baseUrl,
			GLOBAL_API_MODEL_ID: modelId
		});
		show = false;
	};
</script>

<Modal size="sm" bind:show>
	<div>
		<div class="flex justify-between dark:text-gray-100 px-5 pt-4 pb-1.5">
			<h1 class="text-lg font-medium self-center font-primary">
				{$i18n.t('Summary API Configuration')}
			</h1>
			<button
				class="self-center"
				aria-label={$i18n.t('Close modal')}
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="flex flex-col w-full px-5 pb-4 dark:text-gray-200">
			<form
				class="flex flex-col w-full space-y-3"
				on:submit|preventDefault={submitHandler}
			>
				<div>
					<label class="block text-sm font-medium mb-1.5">
						{$i18n.t('Summary API Key')}
					</label>
					<input
						class="w-full rounded-lg py-2 px-3 text-sm bg-transparent border border-gray-300 dark:border-gray-600"
						bind:value={apiKey}
						placeholder={$i18n.t('Enter API Key')}
					/>
				</div>

				<div>
					<label class="block text-sm font-medium mb-1.5">
						{$i18n.t('Base URL')}
					</label>
					<input
						class="w-full rounded-lg py-2 px-3 text-sm bg-transparent border border-gray-300 dark:border-gray-600"
						type="text"
						bind:value={baseUrl}
						placeholder={$i18n.t('Enter Base URL')}
					/>
				</div>

				<div>
					<label class="block text-sm font-medium mb-1.5">
						{$i18n.t('Model ID')}
					</label>
					<input
						class="w-full rounded-lg py-2 px-3 text-sm bg-transparent border border-gray-300 dark:border-gray-600"
						type="text"
						bind:value={modelId}
						placeholder={$i18n.t('Enter Model ID')}
					/>
				</div>

				<div class="flex justify-end pt-3">
					<button
						class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
						type="submit"
					>
						{$i18n.t('Save')}
					</button>
				</div>
			</form>
		</div>
	</div>
</Modal>

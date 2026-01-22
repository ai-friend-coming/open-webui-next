<script lang="ts">
	import {
		models,
		userModels,
		showSettings,
		settings,
		user,
		config
	} from '$lib/stores';
	import { onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Selector from './ModelSelector/Selector.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Modal from '$lib/components/common/Modal.svelte';

	import { updateUserSettings } from '$lib/apis/users';
	import {
	listUserModels,
	createUserModel,
	updateUserModel,
	deleteUserModel,
	testUserModel
	} from '$lib/apis/userModels';

let showUserModelModal = false;
let editingCredential = null;
let form = {
	name: '',
	model_id: '',
	base_url: '',
	api_key: ''
};
let originalForm = null; // 保存编辑时的原始表单数据
let testingConnection = false;
let connectionVerified = false; // 跟踪API连接是否已验证
const i18n = getContext('i18n');

	export let selectedModels = [''];
	export let disabled = false;

	export let showSetDefault = true;

	const saveDefaultModel = async () => {
		const hasEmptyModel = selectedModels.filter((it) => it === '');
		if (hasEmptyModel.length) {
			toast.error($i18n.t('Choose a model before saving...'));
			return;
		}
		settings.set({ ...$settings, models: selectedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });

		toast.success($i18n.t('Default model updated'));
	};

	const pinModelHandler = async (modelId) => {
		let pinnedModels = $settings?.pinnedModels ?? [];

		if (pinnedModels.includes(modelId)) {
			pinnedModels = pinnedModels.filter((id) => id !== modelId);
		} else {
			pinnedModels = [...new Set([...pinnedModels, modelId])];
		}

		settings.set({ ...$settings, pinnedModels: pinnedModels });
		await updateUserSettings(localStorage.token, { ui: $settings });
	};

	$: if (selectedModels.length > 0 && ($models.length > 0 || $userModels.length > 0)) {
		const allIds = [
			...$models.map((m) => m.id),
			...$userModels.map((m) => m.id)
		];

		const _selectedModels = selectedModels.map((model) => (allIds.includes(model) ? model : ''));

		if (JSON.stringify(_selectedModels) !== JSON.stringify(selectedModels)) {
			selectedModels = _selectedModels;
		}
	}

	// 检查关键字段是否被修改（编辑模式下）
	$: hasKeyFieldsChanged = editingCredential && originalForm && (
		form.model_id !== originalForm.model_id ||
		form.api_key !== originalForm.api_key ||
		form.base_url !== originalForm.base_url
	);

	// 当关键字段变化时，重置验证状态
	$: if (hasKeyFieldsChanged) {
		connectionVerified = false;
	}

	const loadUserModels = async () => {
		const res = await listUserModels(localStorage.token).catch((err) => {
			console.error(err);
			return [];
		});
		userModels.set(
			(res ?? []).map((item) => ({
				...item,
				id: `user:${item.id}`, // 前端区分私有模型 ID
				source: 'user'
			}))
		);
	};

	onMount(async () => {
		await loadUserModels();
	});

	const resetForm = () => {
		form = {
			name: '',
			model_id: '',
			base_url: '',
			api_key: ''
		};
		editingCredential = null;
		originalForm = null;
		connectionVerified = false; // 重置验证状态
	};

	const submitUserModel = async () => {
		if (!form.model_id || !form.api_key) {
			toast.error($i18n.t('Model ID and API Key are required'));
			return;
		}

		if (editingCredential) {
			const res = await updateUserModel(localStorage.token, editingCredential, form).catch((err) => {
				toast.error(`${err?.detail ?? err}`);
				return null;
			});
			if (res) {
				toast.success($i18n.t('Updated'));
				await loadUserModels();
			}
		} else {
			const res = await createUserModel(localStorage.token, form).catch((err) => {
				toast.error(`${err?.detail ?? err}`);
				return null;
			});
			if (res) {
				toast.success($i18n.t('Added'));
				await loadUserModels();
			}
		}

		resetForm();
		showUserModelModal = false;
	};

	const testUserModelConnection = async () => {
		if (!form.model_id || !form.api_key) {
			toast.error($i18n.t('Model ID and API Key are required'));
			return;
		}

		testingConnection = true;
		try {
			const res = await testUserModel(localStorage.token, form).catch((err) => {
				toast.error(`${err?.detail ?? err}`);
				connectionVerified = false; // 验证失败，重置状态
				return null;
			});

			if (res) {
				connectionVerified = true; // 验证成功，设置状态为true
				if (res.has_model === false) {
					toast.warning($i18n.t('Connected, but the model ID was not found on the endpoint'));
				} else {
					toast.success($i18n.t('Connection successful'));
				}
			}
		} finally {
			testingConnection = false;
		}
	};

	const removeUserModel = async (cred) => {
		console.log("removeUserModel");
		console.log(cred);
		const res = await deleteUserModel(localStorage.token, cred.id.replace('user:', '')).catch((err) => {
			toast.error(`${err?.detail ?? err}`);
			return null;
		});
		if (res) {
			toast.success($i18n.t('Deleted'));
			await loadUserModels();
		}
	};
</script>


<div class="flex flex-col w-full items-start">
	{#each selectedModels as selectedModel, selectedModelIdx}
		<div class="flex w-full max-w-fit">
			<div class="overflow-hidden w-full">
				<div class="max-w-full {($settings?.highContrastMode ?? false) ? 'm-1' : 'mr-1'}">
					<Selector
						id={`${selectedModelIdx}`}
						placeholder={$i18n.t('Select a model')}
						items={[
							...$models.map((model) => ({
								value: model.id,
								label: model.name,
								model: model,
								source: 'platform'
							})),
							...$userModels.map((model) => ({
								value: model.id,
								label: model.name || model.model_id,
								model: {
									id: model.id,
									name: model.name || model.model_id,
									info: { meta: { description: model.base_url ?? '' } },
									owned_by: 'openai',
									source: 'user'
								},
								source: 'user',
								_credential: model
							}))
						]}
						{pinModelHandler}
						addUserModel={() => {
							resetForm();
							showUserModelModal = true;
						}}
						on:deleteUserModel={(e) => {
							removeUserModel(e.detail);
						}}
						on:editUserModel={(e) => {
							const cred = e.detail._credential;
							editingCredential = cred.id.replace('user:', '');
							form = {
								name: cred.name || '',
								model_id: cred.model_id || '',
								base_url: cred.base_url || '',
								api_key: cred.api_key || ''
							};
							originalForm = { ...form };
							connectionVerified = true; // 编辑已有的credential，默认已验证
							showUserModelModal = true;
						}}
						bind:value={selectedModel}
					/>
				</div>
			</div>

			{#if $user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true)}
				{#if selectedModelIdx === 0}
					<div class="self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]">
						<Tooltip content={$i18n.t('Add Model')}>
								<button
									class=" "
									{disabled}
									on:click={() => {
										selectedModels = [...selectedModels, ''];
									}}
									aria-label="Add Model"
								>
									<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
										<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
									</svg>
								</button>
						</Tooltip>
					</div>
				{:else}
					<div class="self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]">
						<Tooltip content={$i18n.t('Remove Model')}>
							<button
								{disabled}
								on:click={() => {
									selectedModels.splice(selectedModelIdx, 1);
									selectedModels = selectedModels;
								}}
								aria-label="Remove Model"
							>
								<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3">
									<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" />
								</svg>
							</button>
						</Tooltip>
					</div>
				{/if}
			{/if}
		</div>
	{/each}

	<Modal bind:show={showUserModelModal} size="sm" className="bg-white dark:bg-gray-900 rounded-2xl">
		<div class="w-full p-4 space-y-3">
			<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
				{editingCredential ? $i18n.t('Edit My API') : $i18n.t('Add My API')}
			</div>

			<div class="space-y-2 text-sm">
				<div class="flex flex-col gap-1">
					<label class="text-gray-600 dark:text-gray-400">{$i18n.t('Display Name')}</label>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
						bind:value={form.name}
						placeholder={$i18n.t('Optional')}
					/>
				</div>
				<div class="flex flex-col gap-1">
					<label class="text-gray-600 dark:text-gray-400">{$i18n.t('Model ID')}</label>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
						bind:value={form.model_id}
						placeholder="gpt-4o / claude-3..."
					/>
				</div>
				<div class="flex flex-col gap-1">
					<label class="text-gray-600 dark:text-gray-400">{$i18n.t('Base URL')}</label>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
						bind:value={form.base_url}
						placeholder="https://api.openai.com/v1"
					/>
				</div>
				<div class="flex flex-col gap-1">
					<label class="text-gray-600 dark:text-gray-400">API Key</label>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
						bind:value={form.api_key}
						placeholder="sk-..."
					/>
				</div>
			</div>

			<div class="flex justify-end gap-2">
				<button
					class="px-3 py-2 rounded-lg text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
					on:click={() => {
						resetForm();
						showUserModelModal = false;
					}}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="px-3 py-2 rounded-lg text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 disabled:opacity-70"
					on:click={testUserModelConnection}
					disabled={disabled || testingConnection}
				>
					{testingConnection ? $i18n.t('Testing...') : $i18n.t('Verify Connection')}
				</button>
				<button
					class="px-3 py-2 rounded-lg text-sm bg-black text-white dark:bg-white dark:text-black disabled:opacity-50 disabled:cursor-not-allowed"
					on:click={submitUserModel}
					disabled={disabled || testingConnection || (!connectionVerified && (!editingCredential || hasKeyFieldsChanged))}
					title={!connectionVerified && (!editingCredential || hasKeyFieldsChanged) ? $i18n.t('Please verify the connection first') : ''}
				>
					{$i18n.t('Save')}
				</button>
			</div>
		</div>
	</Modal>
</div>

<!-- {#if showSetDefault}
	<div
		class="relative text-left mt-[1px] ml-1 text-[0.7rem] text-gray-600 dark:text-gray-400 font-primary"
	>
		<button on:click={saveDefaultModel}> {$i18n.t('Set as default')}</button>
	</div>
{/if} -->

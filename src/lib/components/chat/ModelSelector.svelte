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
let availableModels = []; // 测试连接后获取的可用模型列表
let isCustomModelId = false; // 是否选择了自定义 Model ID
const i18n = getContext('i18n');

	export let selectedModels = [''];
	export let disabled = false;

	export let showSetDefault = true;

	// Session-specific model name customization
	export let customModelNames = {}; // { "model-id": "Custom Name" }
	export let onRenameModel: (modelId: string, customName: string) => void = () => {};

	let showRenameModal = false;
	let renamingModelId = '';
	let renameForm = { customName: '' };

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
		availableModels = []; // 清空模型列表
		isCustomModelId = false; // 重置自定义标志
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
		if (!form.api_key) {
			toast.error($i18n.t('API Key is required'));
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
				availableModels = res.models || []; // 保存可用模型列表

				// 如果 model_id 为空且有可用模型，自动选择第一个
				if (!form.model_id && availableModels.length > 0) {
					form.model_id = availableModels[0];
				}

				if (res.has_model === false && form.model_id) {
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

	const openRenameModal = (modelId: string) => {
		renamingModelId = modelId;
		renameForm.customName = customModelNames[modelId] || '';
		showRenameModal = true;
	};

	const submitRename = () => {
		if (renameForm.customName.trim() === '') {
			// Clear custom name if empty
			onRenameModel(renamingModelId, '');
		} else {
			onRenameModel(renamingModelId, renameForm.customName.trim());
		}
		showRenameModal = false;
		renamingModelId = '';
		renameForm.customName = '';
	};

	const getDisplayName = (modelId: string) => {
		// Check if there's a custom name for this session
		if (customModelNames[modelId]) {
			return customModelNames[modelId];
		}

		// Otherwise, use the default model name
		const platformModel = $models.find((m) => m.id === modelId);
		if (platformModel) {
			return platformModel.name || modelId;
		}

		const userModel = $userModels.find((m) => m.id === modelId);
		if (userModel) {
			return userModel.name || userModel.model_id || modelId;
		}

		return modelId;
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

			<!-- Rename button for session-specific model name -->
			{#if selectedModel && selectedModel !== ''}
				<div class="self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]">
					<Tooltip content={$i18n.t('Rename model for this chat')}>
						<button
							class="cursor-pointer flex rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition p-1"
							{disabled}
							on:click={() => openRenameModal(selectedModel)}
							aria-label="Rename Model"
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5">
								<path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
							</svg>
						</button>
					</Tooltip>
				</div>
			{/if}

			{#if $user?.role === 'admin' || ($user?.permissions?.chat?.multiple_models ?? true)}
				{#if selectedModelIdx === 0}
					<div class="self-center mx-1 disabled:text-gray-600 disabled:hover:text-gray-600 -translate-y-[0.5px]">
						<Tooltip content={$i18n.t('Add Model')}>
							{#if false}
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
							{/if}
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

			<div class="p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
				<div class="text-sm text-yellow-800 dark:text-yellow-200">
					⚠️ {$i18n.t('暂不支持魔法 API')}
				</div>
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
					{#if !isCustomModelId}
						<select
							class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
							bind:value={form.model_id}
							on:change={(e) => {
								isCustomModelId = e.target.value === '__custom__';
								if (isCustomModelId) {
									form.model_id = '';
								}
							}}
						>
							<option value="" disabled>{$i18n.t('Select a model')}</option>
							{#if availableModels.length > 0}
								<!-- 测试连接后显示 API 返回的模型 -->
								{#each availableModels as model}
									<option value={model}>{model}</option>
								{/each}
							{:else}
								<!-- 默认显示平台模型 -->
								{#each $models as model}
									<option value={model.id}>{model.name}</option>
								{/each}
							{/if}
							<option value="__custom__">{$i18n.t('Other (Custom)')}</option>
						</select>
					{/if}
					{#if isCustomModelId}
						<div class="flex gap-2">
							<input
								class="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
								bind:value={form.model_id}
								placeholder="gpt-4o / claude-3..."
							/>
							<button
								class="px-3 py-2 rounded-lg text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
								on:click={() => {
									isCustomModelId = false;
									form.model_id = '';
								}}
							>
								{$i18n.t('Cancel')}
							</button>
						</div>
					{/if}
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

	<!-- Rename Model Modal -->
	<Modal bind:show={showRenameModal} size="sm" className="bg-white dark:bg-gray-900 rounded-2xl">
		<div class="w-full p-4 space-y-3">
			<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
				{$i18n.t('Rename Model for This Chat')}
			</div>

			<div class="text-sm text-gray-600 dark:text-gray-400">
				{$i18n.t('Set a custom display name for this model in the current chat session. Leave empty to use the default name.')}
			</div>

			<div class="space-y-2 text-sm">
				<div class="flex flex-col gap-1">
					<label class="text-gray-600 dark:text-gray-400">{$i18n.t('Custom Name')}</label>
					<input
						class="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 outline-none"
						bind:value={renameForm.customName}
						placeholder={getDisplayName(renamingModelId)}
						on:keydown={(e) => {
							if (e.key === 'Enter') {
								submitRename();
							}
						}}
					/>
				</div>
			</div>

			<div class="flex justify-end gap-2 pt-2">
				<button
					class="px-3 py-2 rounded-lg text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
					on:click={() => {
						showRenameModal = false;
						renamingModelId = '';
						renameForm.customName = '';
					}}
				>
					{$i18n.t('Cancel')}
				</button>
				<button
					class="px-3 py-2 rounded-lg text-sm bg-black text-white dark:bg-white dark:text-black"
					on:click={submitRename}
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

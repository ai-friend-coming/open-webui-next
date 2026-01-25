<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';

	import dayjs from 'dayjs';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	dayjs.extend(localizedFormat);

	import { getUserSuggestionFeedbacksByUserId } from '$lib/apis/evaluations';

	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Badge from '$lib/components/common/Badge.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');

	export let show = false;
	export let selectedUser: any;

	type UserSuggestionFeedback = {
		id: string;
		user_id: string;
		content: string;
		contact?: string | null;
		status: string;
		created_at: number;
		updated_at: number;
	};

	let feedbacks: UserSuggestionFeedback[] = [];
	let loading = false;

	const getStatusBadgeType = (status: string) => {
		if (status === 'resolved') return 'success';
		if (status === 'pending') return 'warning';
		return 'info';
	};

	const loadFeedbacks = async () => {
		if (!selectedUser?.id) return;
		loading = true;
		feedbacks = [];

		try {
			feedbacks =
				(await getUserSuggestionFeedbacksByUserId(localStorage.token, selectedUser.id)) ?? [];
		} catch (error: any) {
			toast.error($i18n.t('Failed to load feedbacks') + ': ' + (error?.detail || error));
			feedbacks = [];
		} finally {
			loading = false;
		}
	};

	$: if (show && selectedUser) {
		loadFeedbacks();
	}

	$: if (!show) {
		feedbacks = [];
		loading = false;
	}
</script>

<Modal size="lg" bind:show>
	<div>
		<div class="flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class="text-lg font-medium self-center">
				{$i18n.t('Feedbacks')} - {selectedUser?.name}
			</div>
			<button
				class="self-center"
				on:click={() => {
					show = false;
				}}
			>
				<XMark className={'size-5'} />
			</button>
		</div>

		<div class="px-5 pb-5">
			{#if loading}
				<div class="py-8 flex justify-center">
					<Spinner className="size-5" />
				</div>
			{:else if feedbacks.length === 0}
				<div class="text-center py-8 text-gray-500 dark:text-gray-400">
					{$i18n.t('No feedbacks found')}
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm table-fixed">
						<colgroup>
							<col class="w-[11rem]" />
							<col class="w-[6rem]" />
							<col class="w-[12rem]" />
							<col class="w-auto" />
						</colgroup>
						<thead>
							<tr class="border-b dark:border-gray-700 text-left">
								<th class="py-2 px-2 text-xs font-medium dark:text-gray-300 whitespace-nowrap">
									{$i18n.t('Created at')}
								</th>
								<th class="py-2 px-2 text-xs font-medium dark:text-gray-300 whitespace-nowrap">
									{$i18n.t('Status')}
								</th>
								<th class="py-2 px-2 text-xs font-medium dark:text-gray-300 whitespace-nowrap">
									{$i18n.t('Contact')}
								</th>
								<th class="py-2 px-2 text-xs font-medium dark:text-gray-300">
									{$i18n.t('Content')}
								</th>
							</tr>
						</thead>
						<tbody>
							{#each feedbacks as feedback (feedback.id)}
								<tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
									<td class="py-2 px-2 whitespace-nowrap text-gray-700 dark:text-gray-300 align-top">
										{dayjs(feedback.created_at * 1000).format('LLL')}
									</td>
									<td class="py-2 px-2 align-top">
										<Badge type={getStatusBadgeType(feedback.status)} content={feedback.status} />
									</td>
									<td class="py-2 px-2 text-gray-600 dark:text-gray-400 whitespace-nowrap align-top">
										{feedback.contact || '-'}
									</td>
									<td class="py-2 px-2 text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words align-top">
										{feedback.content}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</div>
</Modal>

<script lang="ts">
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import { updateRedeemCode, type RedeemCode, type RedeemCodeForm } from '$lib/apis/redeem-codes';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let show = false;
	export let code: RedeemCode;
	export let onSuccess: () => void;

	let loading = false;
	let formData: RedeemCodeForm;

	// 初始化表单
	$: if (code && show) {
		formData = {
			code: code.code,
			amount: code.amount,
			max_uses: code.max_uses,
			start_time: code.start_time,
			end_time: code.end_time,
			remark: code.remark || ''
		};
	}

	// 提交表单
	const handleSubmit = async () => {
		// 验证
		if (!formData.code || formData.code.length < 6) {
			toast.error('兑换码至少需要6个字符');
			return;
		}

		if (formData.amount <= 0) {
			toast.error('金额必须大于0');
			return;
		}

		if (formData.max_uses <= 0) {
			toast.error('使用次数必须大于0');
			return;
		}

		if (formData.start_time >= formData.end_time) {
			toast.error('生效时间必须早于失效时间');
			return;
		}

		loading = true;
		try {
			await updateRedeemCode(localStorage.token, code.id, formData);
			toast.success('兑换码更新成功');
			onSuccess();
		} catch (error) {
			toast.error(`更新失败: ${error}`);
		} finally {
			loading = false;
		}
	};
</script>

<Modal bind:show size="md">
	<div class="flex flex-col h-full">
		<!-- 标题 -->
		<div class="px-6 py-4 border-b dark:border-gray-700">
			<h3 class="text-lg font-semibold text-gray-900 dark:text-white">编辑兑换码</h3>
		</div>

		<!-- 表单 -->
		{#if formData}
			<div class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
				<!-- 兑换码 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						兑换码 <span class="text-red-500">*</span>
					</label>
					<input
						type="text"
						bind:value={formData.code}
						placeholder="输入兑换码"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
						maxlength="32"
					/>
				</div>

				<!-- 金额 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						兑换金额（元）<span class="text-red-500">*</span>
					</label>
					<input
						type="number"
						bind:value={formData.amount}
						min="0.01"
						step="0.01"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
						disabled={code.current_uses > 0}
					/>
					{#if code.current_uses > 0}
						<p class="text-xs text-yellow-600 dark:text-yellow-400 mt-1">
							⚠️ 已使用过的兑换码不允许修改金额
						</p>
					{/if}
				</div>

				<!-- 最大使用次数 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						最大使用次数 <span class="text-red-500">*</span>
					</label>
					<input
						type="number"
						bind:value={formData.max_uses}
						min={code.current_uses}
						step="1"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
					/>
					<p class="text-xs text-gray-500 mt-1">
						当前已使用 {code.current_uses} 次，最大次数不能小于已使用次数
					</p>
				</div>

				<!-- 生效时间 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						生效时间 <span class="text-red-500">*</span>
					</label>
					<input
						type="datetime-local"
						value={dayjs.unix(formData.start_time).format('YYYY-MM-DDTHH:mm')}
						on:input={(e) => {
							formData.start_time = Math.floor(new Date(e.currentTarget.value).getTime() / 1000);
						}}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
					/>
				</div>

				<!-- 失效时间 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						失效时间 <span class="text-red-500">*</span>
					</label>
					<input
						type="datetime-local"
						value={dayjs.unix(formData.end_time).format('YYYY-MM-DDTHH:mm')}
						on:input={(e) => {
							formData.end_time = Math.floor(new Date(e.currentTarget.value).getTime() / 1000);
						}}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
					/>
				</div>

				<!-- 备注 -->
				<div>
					<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						备注（可选）
					</label>
					<textarea
						bind:value={formData.remark}
						placeholder="添加备注信息"
						rows="3"
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 resize-none"
					/>
				</div>
			</div>
		{/if}

		<!-- 底部按钮 -->
		<div class="px-6 py-4 border-t dark:border-gray-700 flex justify-end gap-3">
			<button
				type="button"
				class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				on:click={() => (show = false)}
				disabled={loading}
			>
				取消
			</button>
			<button
				type="button"
				class="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
				on:click={handleSubmit}
				disabled={loading}
			>
				{#if loading}
					<Spinner className="size-4" />
				{/if}
				{loading ? '更新中...' : '更新兑换码'}
			</button>
		</div>
	</div>
</Modal>

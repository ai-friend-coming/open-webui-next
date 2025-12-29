<script lang="ts">
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';

	import { createRedeemCode, generateRandomCode, type RedeemCodeForm } from '$lib/apis/redeem-codes';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let show = false;
	export let onSuccess: () => void;

	let loading = false;
	let formData: RedeemCodeForm = {
		code: '',
		amount: 10,
		max_uses: 100,
		start_time: Math.floor(Date.now() / 1000),
		end_time: Math.floor(Date.now() / 1000) + 86400 * 30, // 默认30天后
		remark: ''
	};

	// 生成随机兑换码
	const generateCode = () => {
		formData.code = generateRandomCode(12);
	};

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
			await createRedeemCode(localStorage.token, formData);
			toast.success('兑换码创建成功');
			resetForm();
			onSuccess();
		} catch (error) {
			toast.error(`创建失败: ${error}`);
		} finally {
			loading = false;
		}
	};

	// 重置表单
	const resetForm = () => {
		formData = {
			code: '',
			amount: 10,
			max_uses: 100,
			start_time: Math.floor(Date.now() / 1000),
			end_time: Math.floor(Date.now() / 1000) + 86400 * 30,
			remark: ''
		};
	};

	// 关闭时重置
	$: if (!show) {
		resetForm();
		loading = false;
	}
</script>

<Modal bind:show size="md">
	<div class="flex flex-col h-full">
		<!-- 标题 -->
		<div class="px-6 py-4 border-b dark:border-gray-700">
			<h3 class="text-lg font-semibold text-gray-900 dark:text-white">创建兑换码</h3>
		</div>

		<!-- 表单 -->
		<div class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
			<!-- 兑换码 -->
			<div>
				<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					兑换码 <span class="text-red-500">*</span>
				</label>
				<div class="flex gap-2">
					<input
						type="text"
						bind:value={formData.code}
						placeholder="输入或生成兑换码"
						class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
						maxlength="32"
					/>
					<button
						type="button"
						class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg transition-colors whitespace-nowrap"
						on:click={generateCode}
					>
						随机生成
					</button>
				</div>
				<p class="text-xs text-gray-500 mt-1">6-32个字符，建议使用大写字母和数字</p>
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
					placeholder="10.00"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
				/>
			</div>

			<!-- 最大使用次数 -->
			<div>
				<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					最大使用次数 <span class="text-red-500">*</span>
				</label>
				<input
					type="number"
					bind:value={formData.max_uses}
					min="1"
					step="1"
					placeholder="100"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500"
				/>
				<p class="text-xs text-gray-500 mt-1">每个用户只能使用一次，此处设置总次数限制</p>
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
					placeholder="添加备注信息，如用途、适用对象等"
					rows="3"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 resize-none"
				/>
			</div>
		</div>

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
				{loading ? '创建中...' : '创建兑换码'}
			</button>
		</div>
	</div>
</Modal>

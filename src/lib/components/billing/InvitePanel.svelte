<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { formatCurrency } from '$lib/stores';
	import { getInviteInfo, getRebateLogs, getInvitees, type InviteInfo, type InviteRebateLog, type InviteUser } from '$lib/apis/invite';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/stores';

	const i18n = getContext('i18n');

	let inviteInfo: InviteInfo | null = null;
	let rebateLogs: InviteRebateLog[] = [];
	let invitees: InviteUser[] = [];
	let activeTab: 'rebate' | 'invitees' = 'rebate';
	let loading = false;

	// 生成邀请链接
	$: inviteUrl = inviteInfo?.invite_code
		? `${window.location.origin}/auth?mode=signup&invite=${inviteInfo.invite_code}`
		: '';

	onMount(async () => {
		await loadInviteInfo();
		await loadRebateLogs();
	});

	async function loadInviteInfo() {
		try {
			inviteInfo = await getInviteInfo(localStorage.token);
		} catch (error) {
			console.error('Failed to load invite info:', error);
		}
	}

	async function loadRebateLogs() {
		loading = true;
		try {
			const result = await getRebateLogs(localStorage.token, 0, 20);
			rebateLogs = result.logs;
		} catch (error) {
			console.error('Failed to load rebate logs:', error);
		} finally {
			loading = false;
		}
	}

	async function loadInvitees() {
		loading = true;
		try {
			const result = await getInvitees(localStorage.token, 0, 20);
			invitees = result.users;
		} catch (error) {
			console.error('Failed to load invitees:', error);
		} finally {
			loading = false;
		}
	}

	function copyInviteCode() {
		if (inviteInfo?.invite_code) {
			navigator.clipboard.writeText(inviteInfo.invite_code);
			toast.success($i18n.t('邀请码已复制'));
		}
	}

	function copyInviteLink() {
		if (inviteUrl) {
			navigator.clipboard.writeText(inviteUrl);
			toast.success($i18n.t('邀请链接已复制'));
		}
	}

	async function switchTab(tab: 'rebate' | 'invitees') {
		activeTab = tab;
		if (tab === 'invitees' && invitees.length === 0) {
			await loadInvitees();
		}
	}

	function formatDate(timestamp: number): string {
		return new Date(timestamp / 1000000).toLocaleString('zh-CN', {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

{#if inviteInfo}
	<div class="invite-panel">
		<!-- 顶部装饰条 -->
		<div class="panel-header" />

		<div class="panel-content">
			<!-- 标题 -->
			<h3 class="panel-title">{$i18n.t('推广邀请')}</h3>

			<!-- 邀请码区域 -->
			<div class="invite-code-section">
				<div class="invite-code-label">{$i18n.t('我的邀请码')}</div>
				<div class="invite-code-display">
					<span class="invite-code">{inviteInfo.invite_code}</span>
					<button class="copy-btn" on:click={copyInviteCode} title={$i18n.t('复制邀请码')}>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
						</svg>
					</button>
				</div>
				<button class="copy-link-btn" on:click={copyInviteLink}>
					{$i18n.t('复制邀请链接')}
				</button>
			</div>

			<!-- 统计卡片 -->
			<div class="stats-grid">
				<div class="stat-card">
					<div class="stat-label">{$i18n.t('累计邀请')}</div>
					<div class="stat-value">{inviteInfo.total_invitees} {$i18n.t('人')}</div>
				</div>
				<div class="stat-card">
					<div class="stat-label">{$i18n.t('累计返现')}</div>
					<div class="stat-value">{formatCurrency(inviteInfo.total_rebate_amount)}</div>
				</div>
				<div class="stat-card">
					<div class="stat-label">{$i18n.t('返现比例')}</div>
					<div class="stat-value">{inviteInfo.rebate_rate}%</div>
				</div>
			</div>

			<!-- Tab 切换 -->
			<div class="tabs">
				<button
					class="tab"
					class:active={activeTab === 'rebate'}
					on:click={() => switchTab('rebate')}
				>
					{$i18n.t('返现记录')}
				</button>
				<button
					class="tab"
					class:active={activeTab === 'invitees'}
					on:click={() => switchTab('invitees')}
				>
					{$i18n.t('我的邀请')}
				</button>
			</div>

			<!-- 内容区域 -->
			<div class="tab-content">
				{#if loading}
					<div class="loading">{$i18n.t('加载中...')}</div>
				{:else if activeTab === 'rebate'}
					{#if rebateLogs.length > 0}
						<div class="records-list">
							{#each rebateLogs as log}
								<div class="record-item">
									<div class="record-main">
										<div class="record-title">{$i18n.t('充值返现')}</div>
										<div class="record-time">{formatDate(log.created_at)}</div>
									</div>
									<div class="record-amount">+{formatCurrency(log.rebate_amount)}</div>
								</div>
							{/each}
						</div>
					{:else}
						<div class="empty-state">{$i18n.t('暂无返现记录')}</div>
					{/if}
				{:else}
					{#if invitees.length > 0}
						<div class="records-list">
							{#each invitees as invitee}
								<div class="record-item">
									<div class="record-main">
										<div class="record-title">{invitee.name}</div>
										<div class="record-time">{formatDate(invitee.created_at * 1000000)}</div>
									</div>
									<div class="record-meta">
										{$i18n.t('消费')}: {formatCurrency(invitee.total_consumed)}
									</div>
								</div>
							{/each}
						</div>
					{:else}
						<div class="empty-state">{$i18n.t('暂无邀请用户')}</div>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.invite-panel {
		border-radius: 1rem;
		background: rgba(255, 255, 255, 0.7);
		backdrop-filter: blur(20px);
		-webkit-backdrop-filter: blur(20px);
		border: 1px solid rgba(255, 255, 255, 0.3);
		box-shadow: 0 8px 32px 0 rgba(99, 102, 241, 0.15);
		overflow: hidden;
	}

	:global(.dark) .invite-panel {
		background: rgba(31, 41, 55, 0.7);
		border: 1px solid rgba(255, 255, 255, 0.1);
		box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
	}

	.panel-header {
		height: 4px;
		background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
	}

	.panel-content {
		padding: 1.5rem;
	}

	.panel-title {
		font-size: 1.25rem;
		font-weight: 600;
		color: #1f2937;
		margin-bottom: 1.5rem;
	}

	:global(.dark) .panel-title {
		color: #f9fafb;
	}

	/* 邀请码区域 */
	.invite-code-section {
		margin-bottom: 1.5rem;
	}

	.invite-code-label {
		font-size: 0.875rem;
		color: #6b7280;
		margin-bottom: 0.5rem;
		font-weight: 500;
	}

	:global(.dark) .invite-code-label {
		color: #9ca3af;
	}

	.invite-code-display {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: rgba(99, 102, 241, 0.1);
		border-radius: 0.5rem;
		border: 1px solid rgba(99, 102, 241, 0.2);
		margin-bottom: 0.75rem;
	}

	:global(.dark) .invite-code-display {
		background: rgba(99, 102, 241, 0.15);
		border-color: rgba(99, 102, 241, 0.3);
	}

	.invite-code {
		flex: 1;
		font-size: 1.25rem;
		font-weight: 700;
		letter-spacing: 0.1em;
		color: #4f46e5;
	}

	:global(.dark) .invite-code {
		color: #818cf8;
	}

	.copy-btn {
		padding: 0.5rem;
		border-radius: 0.375rem;
		background: rgba(99, 102, 241, 0.1);
		color: #4f46e5;
		border: none;
		cursor: pointer;
		transition: all 0.2s;
	}

	.copy-btn:hover {
		background: rgba(99, 102, 241, 0.2);
		transform: scale(1.05);
	}

	:global(.dark) .copy-btn {
		background: rgba(99, 102, 241, 0.2);
		color: #818cf8;
	}

	:global(.dark) .copy-btn:hover {
		background: rgba(99, 102, 241, 0.3);
	}

	.copy-link-btn {
		width: 100%;
		padding: 0.625rem;
		font-size: 0.875rem;
		font-weight: 500;
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		color: white;
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: transform 0.2s;
	}

	.copy-link-btn:hover {
		transform: translateY(-1px);
		box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
	}

	/* 统计卡片 */
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.75rem;
		margin-bottom: 1.5rem;
	}

	@media (max-width: 640px) {
		.stats-grid {
			grid-template-columns: 1fr;
		}
	}

	.stat-card {
		padding: 1rem;
		background: rgba(249, 250, 251, 0.8);
		border-radius: 0.5rem;
		border: 1px solid rgba(229, 231, 235, 0.8);
		text-align: center;
	}

	:global(.dark) .stat-card {
		background: rgba(55, 65, 81, 0.5);
		border-color: rgba(75, 85, 99, 0.5);
	}

	.stat-label {
		font-size: 0.75rem;
		color: #6b7280;
		margin-bottom: 0.25rem;
	}

	:global(.dark) .stat-label {
		color: #9ca3af;
	}

	.stat-value {
		font-size: 1.125rem;
		font-weight: 700;
		color: #1f2937;
	}

	:global(.dark) .stat-value {
		color: #f9fafb;
	}

	/* Tabs */
	.tabs {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
		border-bottom: 2px solid rgba(229, 231, 235, 0.8);
	}

	:global(.dark) .tabs {
		border-bottom-color: rgba(75, 85, 99, 0.5);
	}

	.tab {
		flex: 1;
		padding: 0.75rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: #6b7280;
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		cursor: pointer;
		transition: all 0.2s;
	}

	.tab:hover {
		color: #4f46e5;
	}

	.tab.active {
		color: #4f46e5;
		border-bottom-color: #4f46e5;
	}

	:global(.dark) .tab {
		color: #9ca3af;
	}

	:global(.dark) .tab:hover {
		color: #818cf8;
	}

	:global(.dark) .tab.active {
		color: #818cf8;
		border-bottom-color: #818cf8;
	}

	/* 内容区域 */
	.tab-content {
		min-height: 200px;
	}

	.loading,
	.empty-state {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 200px;
		color: #9ca3af;
		font-size: 0.875rem;
	}

	.records-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.record-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem;
		background: rgba(249, 250, 251, 0.6);
		border-radius: 0.5rem;
		border: 1px solid rgba(229, 231, 235, 0.8);
	}

	:global(.dark) .record-item {
		background: rgba(55, 65, 81, 0.3);
		border-color: rgba(75, 85, 99, 0.5);
	}

	.record-main {
		flex: 1;
	}

	.record-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: #1f2937;
		margin-bottom: 0.25rem;
	}

	:global(.dark) .record-title {
		color: #f9fafb;
	}

	.record-time {
		font-size: 0.75rem;
		color: #9ca3af;
	}

	.record-amount {
		font-size: 1rem;
		font-weight: 700;
		color: #10b981;
	}

	.record-meta {
		font-size: 0.875rem;
		color: #6b7280;
	}

	:global(.dark) .record-meta {
		color: #9ca3af;
	}
</style>

import { WEBUI_API_BASE_URL } from '$lib/constants';

// ========== 类型定义 ==========

export interface InviteInfo {
	invite_code: string;
	total_invitees: number;
	total_rebate_amount: number; // 毫
	rebate_rate: number; // 百分比
}

export interface InviteRebateLog {
	id: string;
	inviter_id: string;
	invitee_id: string;
	recharge_amount: number; // 毫
	rebate_amount: number; // 毫
	rebate_rate: number; // 百分比
	inviter_balance_before: number; // 毫
	inviter_balance_after: number; // 毫
	recharge_log_id: string | null;
	created_at: number; // 纳秒级时间戳
}

export interface InviteUser {
	id: string;
	name: string;
	email: string | null;
	phone: string | null;
	created_at: number;
	balance: number; // 毫
	total_consumed: number; // 毫
}

export interface InviteConfig {
	rebate_rate: number; // 返现比例（百分比）
}

export interface InviteRelationship {
	inviter: {
		id: string;
		name: string;
		email: string | null;
		invite_code: string;
	};
	invitees: Array<{
		id: string;
		name: string;
		email: string | null;
		created_at: number;
	}>;
}

export interface InviteRelationshipsResponse {
	relationships: InviteRelationship[];
	total_inviters: number;
	total_invitees: number;
}

// ========== API函数 ==========

/**
 * 获取当前用户的邀请信息
 */
export const getInviteInfo = async (token: string): Promise<InviteInfo> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/users/invite/info`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * 获取返现记录列表
 */
export const getRebateLogs = async (
	token: string,
	skip: number = 0,
	limit: number = 50
): Promise<{ logs: InviteRebateLog[]; total: number }> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/users/invite/rebate-logs?skip=${skip}&limit=${limit}`,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * 获取我邀请的用户列表
 */
export const getInvitees = async (
	token: string,
	skip: number = 0,
	limit: number = 50
): Promise<{ users: InviteUser[]; total: number }> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/users/invite/invitees?skip=${skip}&limit=${limit}`,
		{
			method: 'GET',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * 获取邀请返现配置（公开接口）
 */
export const getInviteConfig = async (): Promise<InviteConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/configs/invite/config`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json'
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * 更新邀请返现配置（仅管理员）
 */
export const updateInviteConfig = async (
	token: string,
	rebate_rate: number
): Promise<InviteConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/configs/invite/config`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ rebate_rate })
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * 获取所有用户的邀请关系（管理员专用）
 */
export const getAllInviteRelationships = async (
	token: string
): Promise<InviteRelationshipsResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/users/invite/relationships`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

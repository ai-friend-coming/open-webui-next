/**
 * 兑换码 API 客户端
 */

import { WEBUI_API_BASE_URL } from '$lib/constants';

//==================
// TypeScript 接口
//==================

export interface RedeemCodeForm {
	code: string;
	amount: number; // 元
	max_uses: number;
	start_time: number; // 秒级时间戳
	end_time: number; // 秒级时间戳
	remark?: string;
}

export interface RedeemCode {
	id: string;
	code: string;
	amount: number; // 元
	max_uses: number;
	current_uses: number;
	remaining_uses: number;
	start_time: number;
	end_time: number;
	enabled: boolean;
	created_by: string;
	creator_name: string;
	remark?: string;
	created_at: number;
	updated_at: number;
	status: 'pending' | 'active' | 'expired' | 'exhausted' | 'disabled';
}

export interface RedeemCodeListResponse {
	codes: RedeemCode[];
	total: number;
}

export interface RedeemCodeStats {
	total_amount: number; // 元
	total_users: number;
	total_uses: number;
}

export interface RedeemLog {
	id: string;
	code: string;
	user_id: string;
	user_name: string;
	amount: number; // 元
	balance_before: number; // 元
	balance_after: number; // 元
	created_at: number; // 纳秒
}

export interface RedeemResponse {
	amount: number; // 元
	balance: number; // 元
	message: string;
}

//==================
// 管理员 API
//==================

/**
 * 创建兑换码
 */
export const createRedeemCode = async (
	token: string,
	data: RedeemCodeForm
): Promise<RedeemCode> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/create`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '创建兑换码失败');
	}

	return res.json();
};

/**
 * 查询兑换码列表
 */
export const listRedeemCodes = async (
	token: string,
	status?: string,
	skip: number = 0,
	limit: number = 50
): Promise<RedeemCodeListResponse> => {
	const params = new URLSearchParams({
		skip: skip.toString(),
		limit: limit.toString()
	});

	if (status && status !== 'all') {
		params.append('status_filter', status);
	}

	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes?${params}`, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '查询兑换码列表失败');
	}

	return res.json();
};

/**
 * 查询兑换码详情
 */
export const getRedeemCode = async (token: string, codeId: string): Promise<RedeemCode> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}`, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '查询兑换码失败');
	}

	return res.json();
};

/**
 * 更新兑换码
 */
export const updateRedeemCode = async (
	token: string,
	codeId: string,
	data: RedeemCodeForm
): Promise<RedeemCode> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}`, {
		method: 'PUT',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '更新兑换码失败');
	}

	return res.json();
};

/**
 * 删除兑换码
 */
export const deleteRedeemCode = async (token: string, codeId: string): Promise<void> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}`, {
		method: 'DELETE',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '删除兑换码失败');
	}
};

/**
 * 启用/禁用兑换码
 */
export const toggleRedeemCode = async (token: string, codeId: string): Promise<RedeemCode> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}/toggle`, {
		method: 'POST',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '操作失败');
	}

	return res.json();
};

/**
 * 查询兑换码的兑换日志
 */
export const getRedeemCodeLogs = async (
	token: string,
	codeId: string,
	skip: number = 0,
	limit: number = 50
): Promise<RedeemLog[]> => {
	const params = new URLSearchParams({
		skip: skip.toString(),
		limit: limit.toString()
	});

	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}/logs?${params}`, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '查询日志失败');
	}

	return res.json();
};

/**
 * 查询兑换码统计
 */
export const getRedeemCodeStats = async (
	token: string,
	codeId: string
): Promise<RedeemCodeStats> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/${codeId}/stats`, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '查询统计失败');
	}

	return res.json();
};

//==================
// 用户 API
//==================

/**
 * 兑换码兑换
 */
export const redeemCode = async (token: string, code: string): Promise<RedeemResponse> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-codes/redeem`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ code })
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '兑换失败');
	}

	return res.json();
};

/**
 * 查询我的兑换记录
 */
export const getMyRedeemLogs = async (
	token: string,
	skip: number = 0,
	limit: number = 50
): Promise<RedeemLog[]> => {
	const params = new URLSearchParams({
		skip: skip.toString(),
		limit: limit.toString()
	});

	const res = await fetch(`${WEBUI_API_BASE_URL}/redeem-logs/my?${params}`, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json();
		throw new Error(error.detail || '查询兑换记录失败');
	}

	return res.json();
};

//==================
// 工具函数
//==================

/**
 * 生成随机兑换码
 */
export const generateRandomCode = (length: number = 12): string => {
	const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // 排除易混淆字符 0/O, 1/I
	let code = '';
	for (let i = 0; i < length; i++) {
		code += chars.charAt(Math.floor(Math.random() * chars.length));
	}
	return code;
};

/**
 * 格式化兑换码状态
 */
export const formatStatus = (status: string): string => {
	const statusMap: Record<string, string> = {
		pending: '未生效',
		active: '生效中',
		expired: '已过期',
		exhausted: '已用尽',
		disabled: '已禁用'
	};
	return statusMap[status] || status;
};

/**
 * 获取状态颜色
 */
export const getStatusColor = (status: string): string => {
	const colorMap: Record<string, string> = {
		pending: 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20',
		active: 'text-green-600 bg-green-50 dark:bg-green-900/20',
		expired: 'text-gray-600 bg-gray-50 dark:bg-gray-900/20',
		exhausted: 'text-red-600 bg-red-50 dark:bg-red-900/20',
		disabled: 'text-gray-500 bg-gray-100 dark:bg-gray-800'
	};
	return colorMap[status] || 'text-gray-600 bg-gray-50';
};

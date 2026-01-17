import { WEBUI_API_BASE_URL } from '$lib/constants';

// ========== 类型定义 ==========

export interface FirstRechargeBonusConfig {
	enabled: boolean;
	rate: number; // 返现比例（百分比）
	max_amount: number; // 最高返现金额（元）
}

export interface FirstRechargeBonusStats {
	participant_count: number; // 参与人数
	total_recharge: number; // 总充值金额（元）
	total_bonus: number; // 总奖励金额（元）
}

export interface ParticipantItem {
	id: string;
	user_id: string;
	user_name: string;
	user_email?: string;
	recharge_amount: number; // 首充金额（元）
	bonus_amount: number; // 奖励金额（元）
	bonus_rate: number; // 返现比例（整数百分比）
	created_at: number; // 参与时间（纳秒时间戳）
}

export interface ParticipantListResponse {
	participants: ParticipantItem[];
	total: number;
}

export interface EligibilityResponse {
	eligible: boolean;
	reason?: string;
}

// ========== API 函数 ==========

/**
 * 获取首充优惠配置（仅管理员）
 */
export const getFirstRechargeBonusConfig = async (
	token: string
): Promise<FirstRechargeBonusConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/first-recharge-bonus/config`, {
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
 * 更新首充优惠配置（仅管理员）
 */
export const updateFirstRechargeBonusConfig = async (
	token: string,
	config: FirstRechargeBonusConfig
): Promise<FirstRechargeBonusConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/first-recharge-bonus/config`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(config)
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
 * 获取首充优惠统计（仅管理员）
 */
export const getFirstRechargeBonusStats = async (
	token: string
): Promise<FirstRechargeBonusStats> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/first-recharge-bonus/stats`, {
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
 * 获取首充优惠参与者列表（仅管理员）
 */
export const getFirstRechargeBonusParticipants = async (
	token: string,
	limit: number = 50,
	offset: number = 0
): Promise<ParticipantListResponse> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/first-recharge-bonus/participants?limit=${limit}&offset=${offset}`,
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
 * 检查当前用户是否有资格参与首充优惠
 */
export const checkFirstRechargeBonusEligibility = async (
	token: string
): Promise<EligibilityResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/first-recharge-bonus/eligibility`, {
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

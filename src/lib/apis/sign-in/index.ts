import { WEBUI_API_BASE_URL } from '$lib/constants';

// ========== 类型定义 ==========

export interface SignInConfig {
	enabled: boolean;
	mean: number;
	std: number;
	min_amount: number;
	max_amount: number;
}

export interface SignInResponse {
	success: boolean;
	amount: number;
	message: string;
	continuous_days: number;
}

export interface SignInStatus {
	has_signed_today: boolean;
	continuous_days: number;
	total_days: number;
	total_amount: number;
	month_days: number;
}

export interface SignInLog {
	id: string;
	amount: number;
	sign_in_date: string;
	created_at: number;
}

export interface PublicConfig {
	enabled: boolean;
}

// ========== API函数 ==========

/**
 * 执行每日签到
 */
export const signIn = async (token: string): Promise<SignInResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/sign-in`, {
		method: 'POST',
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
 * 获取签到状态
 */
export const getSignInStatus = async (token: string): Promise<SignInStatus> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/sign-in/status`, {
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
 * 获取签到记录
 */
export const getSignInLogs = async (
	token: string,
	limit: number = 30,
	offset: number = 0
): Promise<SignInLog[]> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/sign-in/logs?limit=${limit}&offset=${offset}`,
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
 * 获取公开配置（无需登录）
 */
export const getPublicConfig = async (): Promise<PublicConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/sign-in/config/public`, {
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
 * 获取签到配置（管理员）
 */
export const getSignInConfig = async (token: string): Promise<SignInConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/sign-in/config`, {
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
 * 更新签到配置（管理员）
 */
export const updateSignInConfig = async (
	token: string,
	config: SignInConfig
): Promise<SignInConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/sign-in/config`, {
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

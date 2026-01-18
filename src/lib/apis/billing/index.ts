import { WEBUI_API_BASE_URL } from '$lib/constants';

// ========== 类型定义 ==========

export interface BalanceInfo {
	balance: number;
	total_consumed: number;
	billing_status: 'active' | 'frozen';
}

export interface BillingLog {
	id: string;
	model_id: string;
	cost: number;
	balance_after: number | null;
	type: 'deduct' | 'refund' | 'precharge' | 'settle';
	prompt_tokens: number;
	completion_tokens: number;
	created_at: number;
	precharge_id?: string | null; // 预扣费事务ID，用于关联 precharge 和 settle
}

export interface DailyStats {
	date: string;
	cost: number;
	by_model: Record<string, number>;  // 按模型分组的消费
}

export interface ModelStats {
	model: string;
	cost: number;
	count: number;
}

export interface BillingStats {
	daily: DailyStats[];
	by_model: ModelStats[];
	models: string[];  // 所有模型列表（用于堆叠图）
}

export interface ModelPricing {
	model_id: string;
	input_price: number;
	output_price: number;
	source: 'database' | 'default';
}

export interface RechargeRequest {
	user_id: string;
	amount: number;
	remark?: string;
}

export interface RechargeLog {
	id: string;
	user_id: string;
	amount: number;
	operator_id: string;
	operator_name: string;
	remark: string | null;
	created_at: number;
}

// ========== API函数 ==========

/**
 * 查询当前用户余额
 */
export const getBalance = async (token: string): Promise<BalanceInfo> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/balance`, {
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
 * 查询消费记录
 */
export const getBillingLogs = async (
	token: string,
	limit: number = 50,
	offset: number = 0
): Promise<BillingLog[]> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/billing/logs?limit=${limit}&offset=${offset}`,
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
 * 查询统计报表
 */
export const getBillingStats = async (
	token: string,
	days: number = 7,
	granularity: string = 'day'
): Promise<BillingStats> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/stats?days=${days}&granularity=${granularity}`, {
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
 * 查询模型定价
 */
export const getModelPricing = async (modelId: string): Promise<ModelPricing> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/pricing/${modelId}`, {
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
 * 列出所有模型定价
 */
export const listModelPricing = async (): Promise<ModelPricing[]> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/pricing`, {
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
 * 管理员充值（仅管理员）
 */
export const rechargeUser = async (
	token: string,
	data: RechargeRequest
): Promise<{ balance: number; status: string }> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/recharge`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
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
 * 设置模型定价（仅管理员）
 */
export const setModelPricing = async (
	token: string,
	data: { model_id: string; input_price: number; output_price: number }
): Promise<ModelPricing> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/pricing`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
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
 * 查询用户充值记录 (仅管理员)
 */
export const getRechargeLogsByUserId = async (
	token: string,
	userId: string,
	limit: number = 50,
	offset: number = 0
): Promise<RechargeLog[]> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/billing/recharge/logs/${userId}?limit=${limit}&offset=${offset}`,
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

// ========== 支付相关 API ==========

export interface CreateOrderResponse {
	order_id: string;
	out_trade_no: string;
	pay_url: string; // 支付宝收银台跳转URL
	amount: number;
	expired_at: number;
}

export interface CreateH5OrderResponse {
	order_id: string;
	out_trade_no: string;
	pay_url: string;
	amount: number;
	expired_at: number;
}

export interface OrderStatusResponse {
	order_id: string;
	status: string;
	amount: number;
	paid_at: number | null;
	is_first_recharge?: boolean;
	bonus_amount?: number;
	bonus_rate?: number;
}

export interface PaymentOrder {
	id: string;
	out_trade_no: string; // 商户订单号
	trade_no: string | null; // 支付宝交易号
	amount: number; // 金额（元）
	status: string; // pending/paid/closed/refunded
	payment_method: string;
	paid_at: number | null;
	created_at: number;
	is_first_recharge?: boolean; // 是否为首充订单
	bonus_amount?: number; // 首充奖励金额（元）
}

export interface PaymentConfig {
	alipay_enabled: boolean;
}

/**
 * 获取支付配置状态
 */
export const getPaymentConfig = async (): Promise<PaymentConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/payment/config`, {
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
 * 获取用户支付订单列表
 */
export const getPaymentOrders = async (
	token: string,
	limit: number = 50,
	offset: number = 0
): Promise<PaymentOrder[]> => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/billing/payment/orders?limit=${limit}&offset=${offset}`,
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
 * 创建充值订单
 */
export const createPaymentOrder = async (
	token: string,
	amount: number
): Promise<CreateOrderResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/payment/create`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ amount })
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
 * 创建H5充值订单（移动端跳转支付）
 */
export const createH5PaymentOrder = async (
	token: string,
	amount: number
): Promise<CreateH5OrderResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/payment/create/h5`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({ amount })
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
 * 查询订单状态
 */
export const getPaymentStatus = async (
	token: string,
	orderId: string
): Promise<OrderStatusResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/billing/payment/status/${orderId}`, {
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

// ========== 首充优惠 API ==========

export interface FirstRechargeBonusConfig {
	enabled: boolean;
	rate: number; // 返现比例（百分比）
	max_amount: number; // 最高返现金额（元）
}

export interface FirstRechargeBonusEligibility {
	eligible: boolean;
	reason?: string;
}

/**
 * 获取首充优惠配置（公开接口）
 */
export const getFirstRechargeBonusConfig = async (): Promise<FirstRechargeBonusConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/first-recharge-bonus/config/public`, {
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
 * 检查用户首充资格
 */
export const checkFirstRechargeBonusEligibility = async (
	token: string
): Promise<FirstRechargeBonusEligibility> => {
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

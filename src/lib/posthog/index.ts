import posthog from 'posthog-js';

export const initPosthog = () => {
	if (typeof window === 'undefined') {
		return;
	}

	posthog.init('phc_Abmjxrycc5WX5tnegaHmQx5COrSTFmM72VmyDVv4xCa', {
		api_host: 'https://us.i.posthog.com',
		defaults: '2025-11-30',
		person_profiles: 'identified_only',
		autocapture: false, // 禁用点击、输入、表单提交等交互事件
		session_recording: {
			maskAllInputs: false,
			maskTextSelector: '.sensitive, .private, [data-sensitive="true"]'
		}
	});
};

export const signInTracking = (sessionUser: {
	id: string;
	email: string;
	name: string;
}) => {
	if (typeof window === 'undefined' || !sessionUser) {
		return;
	}

	posthog.identify(sessionUser.id, {
		email: sessionUser.email,
		name: sessionUser.name
	});
	posthog.capture('user_logged_in');
};

export const logOutTracking = (metadata: { reason?: string } = {}) => {
	if (typeof window === 'undefined') {
		return;
	}

	posthog.capture('user_logged_out', metadata);
	posthog.reset();
};

export const initTabTracking = () => {
	if (typeof window === 'undefined') {
		return null;
	}

	let isTabVisible = true;
	const tabId =
		sessionStorage.getItem('tab_id') || `${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

	sessionStorage.setItem('tab_id', tabId);

	posthog.register({
		tab_id: tabId,
		tab_opened_at: new Date().toISOString()
	});

	const heartbeatIntervalMs = 30 * 60 * 1000;

	// 心跳
	const heartbeatId = window.setInterval(() => {
		posthog.capture('tab_heartbeat', {
			page_url: window.location.href,
			visibility_state: document.visibilityState
		});
	}, heartbeatIntervalMs);

	// 🔑 1. 标签页可见性变化（切换标签页）
	const handleVisibilityChange = () => {
		const wasVisible = isTabVisible;
		isTabVisible = !document.hidden;

		if (document.visibilityState === 'hidden') {
			posthog.capture('tab_hidden', {
				page_url: window.location.href,
				time_visible: performance.now()
			});
		} else if (document.visibilityState === 'visible') {
			posthog.capture('tab_visible', {
				page_url: window.location.href,
				was_hidden_duration: wasVisible ? 0 : performance.now()
			});
		}
	};

	// 🔑 2. 监听窗口失去焦点（用户点击了其他应用）
	const handleBlur = () => {
		posthog.capture('window_blur', {
			page_url: window.location.href
		});
	};

	// 🔑 3. 监听窗口获得焦点
	const handleFocus = () => {
		posthog.capture('window_focus', {
			page_url: window.location.href
		});
	};

	// 🔑 4. 页面卸载（兼容性备选）
	const handleBeforeUnload = () => {
		posthog.capture('$pageleave', {
			$current_url: window.location.href
		});
	};

	// 🔑 5. 页面隐藏（关闭标签页或导航离开）
	const handlePageHide = (event: PageTransitionEvent) => {
		posthog.capture('page_hide', {
			page_url: window.location.href,
			persisted: event.persisted
		});
	};

	document.addEventListener('visibilitychange', handleVisibilityChange);
	window.addEventListener('blur', handleBlur);
	window.addEventListener('focus', handleFocus);
	window.addEventListener('beforeunload', handleBeforeUnload);
	window.addEventListener('pagehide', handlePageHide);

	return () => {
		window.clearInterval(heartbeatId);
		document.removeEventListener('visibilitychange', handleVisibilityChange);
		window.removeEventListener('blur', handleBlur);
		window.removeEventListener('focus', handleFocus);
		window.removeEventListener('beforeunload', handleBeforeUnload);
		window.removeEventListener('pagehide', handlePageHide);
	};
};

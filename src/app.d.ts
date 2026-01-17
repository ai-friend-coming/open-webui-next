// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}

	// Vite define 全局变量类型声明
	const APP_VERSION: string;
	const APP_BUILD_HASH: string;
	const APP_BUILD_BRANCH: string;
}

export {};

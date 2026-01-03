<script lang="ts">
	/**
	 * 流式解密示例组件
	 *
	 * 展示如何在流式输出时实时解密文本
	 * 可集成到 ResponseMessage.svelte 中
	 */
	import { onMount, onDestroy } from 'svelte';
	import { streamDecrypt, isEncryptionEnabled } from '$lib/utils/crypto';
	import EncryptionIndicator from './EncryptionIndicator.svelte';

	// 组件属性
	export let encryptedContent: string = ''; // 从后端接收的加密内容
	export let keepEncryptedChars: number = 10; // 保持密文的字符数

	// 状态变量
	let decryptedText: string = ''; // 已解密的文本
	let encryptedText: string = ''; // 仍保持密文的部分
	let isDecrypting: boolean = false; // 是否正在解密
	let decryptionError: string | null = null; // 解密错误

	// 解密定时器
	let decryptTimer: NodeJS.Timeout | null = null;

	/**
	 * 执行流式解密
	 */
	async function performDecryption() {
		if (!encryptedContent || !isEncryptionEnabled()) {
			// 如果没有加密或未启用加密，直接显示原文
			decryptedText = encryptedContent;
			encryptedText = '';
			return;
		}

		isDecrypting = true;
		decryptionError = null;

		try {
			// 调用流式解密函数
			const result = await streamDecrypt([encryptedContent], keepEncryptedChars);

			decryptedText = result.decrypted;
			encryptedText = result.encrypted;
		} catch (error) {
			console.error('[StreamDecrypt] Decryption failed:', error);
			decryptionError = '解密失败';
			// 失败时显示原始密文
			decryptedText = '';
			encryptedText = encryptedContent;
		} finally {
			isDecrypting = false;
		}
	}

	/**
	 * 防抖解密：避免频繁调用解密
	 */
	function scheduleDecryption() {
		// 清除之前的定时器
		if (decryptTimer) {
			clearTimeout(decryptTimer);
		}

		// 设置新的定时器（100ms 防抖）
		decryptTimer = setTimeout(() => {
			performDecryption();
		}, 100);
	}

	// 监听加密内容变化
	$: if (encryptedContent) {
		scheduleDecryption();
	}

	// 清理定时器
	onDestroy(() => {
		if (decryptTimer) {
			clearTimeout(decryptTimer);
		}
	});
</script>

<div class="stream-decrypt-container">
	<!-- 已解密的文本（明文） -->
	{#if decryptedText}
		<span class="decrypted-text">{decryptedText}</span>
	{/if}

	<!-- 仍保持密文的部分 -->
	{#if encryptedText}
		<span class="encrypted-text font-mono text-gray-400 dark:text-gray-600">
			{encryptedText}
		</span>
	{/if}

	<!-- 加密传输指示器 -->
	{#if isDecrypting || encryptedText}
		<EncryptionIndicator show={true} variant="inline" />
	{/if}

	<!-- 解密错误提示 -->
	{#if decryptionError}
		<span class="error-text text-red-500 text-xs ml-2">
			({decryptionError})
		</span>
	{/if}
</div>

<style>
	.stream-decrypt-container {
		display: inline;
	}

	.decrypted-text {
		/* 明文样式 */
	}

	.encrypted-text {
		/* 密文样式：等宽字体，灰色 */
		letter-spacing: 0.05em;
	}
</style>

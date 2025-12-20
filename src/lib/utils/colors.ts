// 预定义的高区分度颜色调色板（30色）
const MODEL_PALETTE = [
	// 主色调
	'#4F46E5', // indigo
	'#10B981', // emerald
	'#F59E0B', // amber
	'#EF4444', // red
	'#8B5CF6', // violet
	'#06B6D4', // cyan
	'#EC4899', // pink
	'#84CC16', // lime
	'#F97316', // orange
	'#6366F1', // indigo-light
	// 补充色调
	'#14B8A6', // teal
	'#A855F7', // purple
	'#0EA5E9', // sky
	'#22C55E', // green
	'#E11D48', // rose
	'#7C3AED', // violet-dark
	'#0891B2', // cyan-dark
	'#CA8A04', // yellow-dark
	'#DC2626', // red-dark
	'#059669', // emerald-dark
	// 扩展色调
	'#2563EB', // blue
	'#9333EA', // purple-bright
	'#DB2777', // pink-dark
	'#65A30D', // lime-dark
	'#EA580C', // orange-dark
	'#4338CA', // indigo-dark
	'#0D9488', // teal-dark
	'#B45309', // amber-dark
	'#7E22CE', // purple-deep
	'#15803D'  // green-dark
];

// 简单的字符串哈希函数
function hashString(str: string): number {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		const char = str.charCodeAt(i);
		hash = (hash << 5) - hash + char;
		hash = hash & hash; // Convert to 32bit integer
	}
	return Math.abs(hash);
}

// 根据 modelId 获取固定颜色
export function getModelColor(modelId: string): string {
	const hash = hashString(modelId);
	return MODEL_PALETTE[hash % MODEL_PALETTE.length];
}

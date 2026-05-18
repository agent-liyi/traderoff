/**
 * 将 HTML 字符串转为纯文本，保留段落换行结构。
 * 不依赖 DOM，在 Node.js/Edge Runtime 均可运行。
 */
export function htmlToText(html: string): string {
  if (!html) return '';

  return html
    // 块级元素前后加换行
    .replace(/<\/(p|div|section|article|h[1-6]|li|blockquote|tr)>/gi, '\n')
    .replace(/<(br\s*\/?)>/gi, '\n')
    // 列表项加 bullet
    .replace(/<li[^>]*>/gi, '• ')
    // 移除所有剩余标签
    .replace(/<[^>]+>/g, '')
    // 解码常见 HTML 实体
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&hellip;/g, '…')
    .replace(/&mdash;/g, '—')
    .replace(/&ndash;/g, '–')
    // 多余空行合并（保留最多两个连续换行）
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/**
 * 从 HTML 描述中提取纯文本前 N 个字符（用于 meta description）
 */
export function htmlToExcerpt(html: string, maxLength = 150): string {
  const text = htmlToText(html);
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).replace(/\s+\S*$/, '') + '…';
}

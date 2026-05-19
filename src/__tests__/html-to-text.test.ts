import { describe, it, expect } from 'vitest';
import { htmlToText, htmlToExcerpt } from '@/lib/html-to-text';
import { hasDbAudio } from '@/lib/types';

describe('htmlToText', () => {
  it('should return empty string for falsy input', () => {
    expect(htmlToText('')).toBe('');
  });

  it('should strip all HTML tags', () => {
    expect(htmlToText('<p>Hello</p>')).toBe('Hello');
  });

  it('should convert block-level closing tags to newlines', () => {
    const input = '<p>第一段</p><p>第二段</p>';
    expect(htmlToText(input)).toBe('第一段\n第二段');
  });

  it('should convert <br> to newline', () => {
    expect(htmlToText('行1<br>行2')).toBe('行1\n行2');
    expect(htmlToText('行1<br/>行2')).toBe('行1\n行2');
  });

  it('should add bullet for <li>', () => {
    expect(htmlToText('<ul><li>苹果</li><li>香蕉</li></ul>')).toBe('• 苹果\n• 香蕉');
  });

  it('should handle headings as blocks', () => {
    expect(htmlToText('<h1>标题</h1><p>内容</p>')).toBe('标题\n内容');
  });

  it('should decode HTML entities', () => {
    expect(htmlToText('A&amp;B')).toBe('A&B');
    expect(htmlToText('&lt;hello&gt;')).toBe('<hello>');
    expect(htmlToText('a&nbsp;b')).toBe('a b');
    expect(htmlToText('&quot;quote&quot;')).toBe('"quote"');
    expect(htmlToText("it&#39;s")).toBe("it's");
    expect(htmlToText('&hellip;')).toBe('…');
    expect(htmlToText('&mdash;')).toBe('—');
    expect(htmlToText('&ndash;')).toBe('–');
  });

  it('should collapse excessive newlines (3+ → 2)', () => {
    const input = '<p>A</p><br><br><br><p>B</p>';
    const result = htmlToText(input);
    // Should not have 3+ consecutive newlines
    expect(result).not.toMatch(/\n{3,}/);
  });

  it('should handle complex podcast-style content', () => {
    const input =
      '<p>欢迎收听「动态平衡」</p><h2>本期嘉宾</h2><p>今天我们邀请到了<strong>张三</strong></p><ul><li>话题一</li><li>话题二</li></ul><blockquote><p>重要的引用</p></blockquote>';
    const result = htmlToText(input);
    expect(result).toContain('欢迎收听「动态平衡」');
    expect(result).toContain('本期嘉宾');
    expect(result).toContain('张三');
    expect(result).toContain('• 话题一');
    expect(result).toContain('• 话题二');
    expect(result).toContain('重要的引用');
  });

  it('should trim leading/trailing whitespace', () => {
    expect(htmlToText('<p>  hello  </p>')).toBe('hello');
  });
});

describe('htmlToExcerpt', () => {
  it('should return empty string for empty input', () => {
    expect(htmlToExcerpt('')).toBe('');
  });

  it('should return full text if shorter than maxLength', () => {
    expect(htmlToExcerpt('<p>短文本</p>', 50)).toBe('短文本');
  });

  it('should truncate at maxLength', () => {
    const text = 'A'.repeat(200);
    expect(htmlToExcerpt(text, 50).length).toBeLessThanOrEqual(53); // 50 + '…'
    expect(htmlToExcerpt(text, 50)).toMatch(/…$/);
  });

  it('should break at word boundary when truncating', () => {
    const input = '<p>这是一段比较长的文本内容需要被截断然后显示省略号</p>';
    const result = htmlToExcerpt(input, 10);
    // Should not break in the middle of a word
    expect(result).not.toMatch(/断[^…]…/);
  });

  it('should use default maxLength of 150', () => {
    const input = '<p>' + '很'.repeat(200) + '</p>';
    const result = htmlToExcerpt(input);
    expect(result.length).toBeLessThanOrEqual(153);
  });

  it('should strip HTML before applying excerpt logic', () => {
    const input = '<p><strong>Hello</strong> <em>World</em></p>';
    const result = htmlToExcerpt(input, 20);
    expect(result).toBe('Hello World');
    expect(result).not.toContain('<');
  });
});

describe('hasDbAudio', () => {
  const baseEpisode = {
    id: 1, episode_number: 'S1E01', title: 'test', guest: null,
    description: null, transcript: null, cover_image: null, duration: null,
    publish_date: null, link_xiaoyuzhou: null, link_apple_podcasts: null,
    audio_url: null, audio_data: null as number[] | null,
    created_at: '', updated_at: '',
  };

  it('有音频数据时返回 true', () => {
    expect(hasDbAudio({ ...baseEpisode, audio_data: [1, 2, 3] })).toBe(true);
  });

  it('audio_data 为 null 返回 false', () => {
    expect(hasDbAudio({ ...baseEpisode, audio_data: null })).toBe(false);
  });

  it('audio_data 为空数组返回 false', () => {
    expect(hasDbAudio({ ...baseEpisode, audio_data: [] })).toBe(false);
  });
});

import { NextResponse } from 'next/server';
import getDb from '@/lib/db';
import { htmlToExcerpt } from '@/lib/html-to-text';
import { Episode } from '@/lib/types';

export const dynamic = 'force-dynamic';

export async function GET() {
  let episodes: Episode[] = [];
  try {
    const db = getDb();
    episodes = db
      .prepare('SELECT * FROM episodes ORDER BY episode_number ASC')
      .all() as Episode[];
  } catch {
    episodes = [];
  }

  const lines: string[] = [];

  lines.push('# 动态平衡');
  lines.push('');
  lines.push(
    '「动态平衡」是一档关注个人成长与生活方式的中文对话播客。' +
      '每期邀请一位在某个领域有深度思考的嘉宾，聊聊他们如何在快速变化的世界中找到属于自己的节奏与平衡。' +
      '节目每两周更新一期，可在小宇宙、苹果播客、Spotify 等平台收听。'
  );
  lines.push('');
  lines.push('> 主播：李逸（产品设计师）');
  lines.push('> 联系：hello@dongtaipingheng.com');
  lines.push('');
  lines.push('---');
  lines.push('');

  if (episodes.length === 0) {
    lines.push('暂无已发布节目。');
  } else {
    lines.push('## 节目列表');
    lines.push('');
    for (const ep of episodes) {
      lines.push(`### ${ep.episode_number} · ${ep.title}`);
      if (ep.guest) lines.push(`嘉宾：${ep.guest}`);
      if (ep.publish_date) lines.push(`发布日期：${ep.publish_date}`);
      if (ep.duration) lines.push(`时长：${ep.duration}`);
      if (ep.description) {
        const excerpt = htmlToExcerpt(ep.description, 200);
        lines.push('');
        lines.push(excerpt);
      }
      if (ep.link_xiaoyuzhou) lines.push(`小宇宙：${ep.link_xiaoyuzhou}`);
      if (ep.link_apple_podcasts) lines.push(`苹果播客：${ep.link_apple_podcasts}`);
      lines.push(`逐字稿：/episodes/${ep.id}`);
      lines.push('');
    }
  }

  const body = lines.join('\n');

  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
    },
  });
}

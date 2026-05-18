import { createClient } from '@libsql/client';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';

// 加载 .env.local
const envPath = path.join(process.cwd(), '.env.local');
if (fs.existsSync(envPath)) {
  dotenv.config({ path: envPath });
}

const episodes = [
  {
    episode_number: 'S1E03',
    title: '当"效率"成为一种焦虑',
    guest: '张潇',
    description:
      '<p>这期我们聊了一个很多人都有感触的话题：为什么我们对"低效率"有那么强的负罪感？</p><p>张潇是一位独立咨询师，从大厂离开后，她花了很长时间才学会接受"慢下来"。我们聊了时间管理的迷思、休息的正当性，以及如何在"做得不够多"的感受中找到平静。</p>',
    transcript:
      '<h2>开场</h2><p><strong>李逸：</strong>大家好，欢迎来到动态平衡。今天请到的嘉宾是张潇，一位独立咨询师。潇姐，先跟大家打个招呼？</p><p><strong>张潇：</strong>大家好，很开心来到这里。</p><h2>离开大厂后的第一个月</h2><p><strong>李逸：</strong>你是什么时候离开上一份工作的？</p><p><strong>张潇：</strong>去年三月。离开之后第一个月，说实话我不知道该干什么。以前每天日程排满，突然一天没有会了，反而特别焦虑。</p><p><strong>李逸：</strong>那种焦虑具体是什么感觉？</p><p><strong>张潇：</strong>就是坐着看书会觉得自己在浪费时间。明明不用上班了，但还是有种"我应该在做点什么有产出的事"的压力。</p>',
    cover_image: null as string | null,
    duration: '62:30',
    publish_date: '2026/05/14',
    link_xiaoyuzhou: 'https://www.xiaoyuzhoufm.com/episode/example3',
    link_apple_podcasts: 'https://podcasts.apple.com/example3',
    audio_url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3',
  },
  {
    episode_number: 'S1E02',
    title: '远程工作两年后，我对自由的理解变了',
    guest: '刘睿',
    description:
      '<p>刘睿是一位前端工程师，两年前开始全职远程工作。从最初的兴奋到中间的孤独，再到现在的平衡，他的经历可能比很多"远程工作攻略"更真实。</p><p>我们聊了远程工作的真实日常、如何处理社交缺失、以及"自由"这个词被滥用之后还剩下什么。</p>',
    transcript:
      '<h2>开场</h2><p><strong>李逸：</strong>欢迎来到动态平衡第二期，今天的嘉宾是刘睿，一位全职远程的前端工程师。</p><p><strong>刘睿：</strong>大家好！</p><h2>为什么选择远程</h2><p><strong>李逸：</strong>先聊聊你为什么选择远程工作？</p><p><strong>刘睿：</strong>最开始其实是被迫的，疫情嘛。后来发现自己效率更高了，通勤时间省下来可以做很多事。再后来公司说可以选择继续远程，我就选了。</p><p><strong>李逸：</strong>听起来是个自然的过程。</p><p><strong>刘睿：</strong>对，但真正全职远程之后，才发现挑战在后面。最大的问题不是效率，是孤独。</p>',
    cover_image: null as string | null,
    duration: '55:12',
    publish_date: '2026/04/30',
    link_xiaoyuzhou: 'https://www.xiaoyuzhoufm.com/episode/example2',
    link_apple_podcasts: 'https://podcasts.apple.com/example2',
    audio_url: 'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3',
  },
  {
    episode_number: 'S1E01',
    title: '第一期：为什么要做一档叫"动态平衡"的播客',
    guest: null as string | null,
    description:
      '<p>这是动态平衡的第一期节目，没有嘉宾，就是我自己聊聊为什么想做这档播客。</p><p>在快速变化的环境里，"平衡"不是一个终点，而是一种持续调整的能力。我想通过对话来探索这个主题——和不同的人聊聊他们是怎么在变化中找到自己节奏的。</p>',
    transcript:
      '<h2>开场</h2><p><strong>李逸：</strong>嗨，大家好。欢迎来到动态平衡的第一期。今天没有嘉宾，就是我自己来聊聊这档播客是怎么回事。</p><h2>为什么叫动态平衡</h2><p>这个名字来自化学里的一个概念。动态平衡不是静止的，而是两个方向的变化速率相等时呈现出的一种稳定状态。我觉得生活也是这样。</p><p>我们不太可能找到一个完美的平衡点然后一直待着不动。更现实的做法是学会不断调整——工作重了就多休息，社交多了就给自己独处的时间。这种持续的调整本身，就是平衡。</p>',
    cover_image: null as string | null,
    duration: '28:45',
    publish_date: '2026/04/16',
    link_xiaoyuzhou: 'https://www.xiaoyuzhoufm.com/episode/example1',
    link_apple_podcasts: 'https://podcasts.apple.com/example1',
    audio_url: null as string | null,
  },
];

async function main() {
  // 确保本地 data/ 目录存在
  const dataDir = path.join(process.cwd(), 'data');
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  const db = createClient({
    url: process.env.TURSO_DATABASE_URL || 'file:./data/podcast.db',
    authToken: process.env.TURSO_AUTH_TOKEN,
  });

  // Create table
  await db.execute(`
    CREATE TABLE IF NOT EXISTS episodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      episode_number TEXT NOT NULL,
      title TEXT NOT NULL,
      guest TEXT,
      description TEXT,
      transcript TEXT,
      cover_image TEXT,
      duration TEXT,
      publish_date TEXT,
      link_xiaoyuzhou TEXT,
      link_apple_podcasts TEXT,
      audio_url TEXT,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Clear existing data
  await db.execute('DELETE FROM episodes');

  for (const ep of episodes) {
    await db.execute({
      sql: `INSERT INTO episodes (episode_number, title, guest, description, transcript, cover_image, duration, publish_date, link_xiaoyuzhou, link_apple_podcasts, audio_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [
        ep.episode_number,
        ep.title,
        ep.guest,
        ep.description,
        ep.transcript,
        ep.cover_image,
        ep.duration,
        ep.publish_date,
        ep.link_xiaoyuzhou,
        ep.link_apple_podcasts,
        ep.audio_url,
      ],
    });
  }

  console.log(`✅ Seeded ${episodes.length} episodes successfully`);
  console.log(`   URL: ${process.env.TURSO_DATABASE_URL || 'file:./data/podcast.db'}`);

  db.close();
}

main().catch((err) => {
  console.error('❌ Seed failed:', err);
  process.exit(1);
});

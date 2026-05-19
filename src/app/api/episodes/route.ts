import { NextRequest, NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import path from 'path';
import db from '@/lib/db';
import { Episode } from '@/lib/types';

/** 如果 audio_url 指向本地文件，读入并作为 BLOB 存入 DB */
async function storeAudioBlob(episodeId: number, audioUrl: string | null) {
  if (!audioUrl || !audioUrl.startsWith('/uploads/')) return;
  try {
    const filePath = path.join(process.cwd(), 'public', audioUrl);
    const buffer = readFileSync(filePath);
    await db.execute({
      sql: 'UPDATE episodes SET audio_data = ? WHERE id = ?',
      args: [buffer, episodeId],
    });
  } catch (e) {
    console.error('Failed to store audio BLOB:', e);
  }
}

export async function GET() {
  try {
    const result = await db.execute('SELECT * FROM episodes ORDER BY id DESC');
    const episodes = result.rows as unknown as Episode[];
    return NextResponse.json(episodes);
  } catch (error) {
    console.error('Failed to get episodes:', error);
    return NextResponse.json([], { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    await db.execute({
      sql: `INSERT INTO episodes (episode_number, title, guest, description, transcript, cover_image, duration, publish_date, link_xiaoyuzhou, link_apple_podcasts, audio_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [
        body.episode_number,
        body.title,
        body.guest || null,
        body.description || null,
        body.transcript || null,
        body.cover_image || null,
        body.duration || null,
        body.publish_date || null,
        body.link_xiaoyuzhou || null,
        body.link_apple_podcasts || null,
        body.audio_url || null,
      ],
    });

    const inserted = await db.execute({
      sql: 'SELECT * FROM episodes ORDER BY id DESC LIMIT 1',
      args: [],
    });

    const episode = inserted.rows[0] as unknown as Episode;

    // 将本地音频文件存入 BLOB 列
    await storeAudioBlob(episode.id, body.audio_url || null);

    return NextResponse.json(episode, { status: 201 });
  } catch (error) {
    console.error('Failed to create episode:', error);
    return NextResponse.json(
      { error: 'Failed to create episode' },
      { status: 500 }
    );
  }
}

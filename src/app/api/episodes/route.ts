import { NextRequest, NextResponse } from 'next/server';
import db from '@/lib/db';
import { Episode } from '@/lib/types';

/** 将 base64 字符串解码为 Buffer，存入 audio_data BLOB */
async function storeAudioFromBase64(episodeId: number, base64: string | null) {
  if (!base64) return;
  try {
    const buffer = Buffer.from(base64, 'base64');
    if (buffer.length === 0) return;
    await db.execute({
      sql: 'UPDATE episodes SET audio_data = ? WHERE id = ?',
      args: [buffer, episodeId],
    });
  } catch (e) {
    console.error('Failed to store audio BLOB from base64:', e);
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
    const { audio_base64, ...episodeData } = body;

    await db.execute({
      sql: `INSERT INTO episodes (episode_number, title, guest, description, transcript, cover_image, duration, publish_date, link_xiaoyuzhou, link_apple_podcasts, audio_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      args: [
        episodeData.episode_number,
        episodeData.title,
        episodeData.guest || null,
        episodeData.description || null,
        episodeData.transcript || null,
        episodeData.cover_image || null,
        episodeData.duration || null,
        episodeData.publish_date || null,
        episodeData.link_xiaoyuzhou || null,
        episodeData.link_apple_podcasts || null,
        episodeData.audio_url || null,
      ],
    });

    const inserted = await db.execute({
      sql: 'SELECT * FROM episodes ORDER BY id DESC LIMIT 1',
      args: [],
    });

    const episode = inserted.rows[0] as unknown as Episode;

    // 将 base64 音频数据解码存入 BLOB 列
    await storeAudioFromBase64(episode.id, audio_base64 || null);

    return NextResponse.json(episode, { status: 201 });
  } catch (error) {
    console.error('Failed to create episode:', error);
    return NextResponse.json(
      { error: 'Failed to create episode' },
      { status: 500 }
    );
  }
}

import { NextRequest, NextResponse } from 'next/server';
import { readFile, unlink } from 'fs/promises';
import { existsSync } from 'fs';
import db from '@/lib/db';
import { Episode } from '@/lib/types';

/** 将临时音频文件读入 BLOB 并删除临时文件 */
async function storeAudioFromFile(episodeId: number, filePath: string | null) {
  if (!filePath || !existsSync(filePath)) return;
  try {
    const buffer = await readFile(filePath);
    if (buffer.length === 0) return;
    await db.execute({
      sql: 'UPDATE episodes SET audio_data = ? WHERE id = ?',
      args: [buffer, episodeId],
    });
    // 存入数据库后删除临时文件
    await unlink(filePath).catch(() => {});
    console.log(`Audio stored for episode ${episodeId}: ${buffer.length} bytes`);
  } catch (e: any) {
    console.error('Failed to store audio BLOB:', e.message);
    throw e;
  }
}

export async function GET() {
  try {
    const result = await db.execute('SELECT * FROM episodes ORDER BY id DESC');
    const episodes = (result.rows as unknown as Episode[]).map((row: any) => ({
      ...row,
      audio_data: undefined,
      has_db_audio: !!(row.audio_data),
    }));
    return NextResponse.json(episodes);
  } catch (error: any) {
    console.error('Failed to get episodes:', error);
    return NextResponse.json(
      { error: `读取节目列表失败: ${error.message}` },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { audio_path, audio_base64, ...episodeData } = body;

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

    // 从临时文件读入 BLOB（优先新方式，兼容旧 base64）
    if (audio_path) {
      await storeAudioFromFile(episode.id, audio_path);
    } else if (audio_base64) {
      try {
        const buffer = Buffer.from(audio_base64, 'base64');
        if (buffer.length > 0) {
          await db.execute({
            sql: 'UPDATE episodes SET audio_data = ? WHERE id = ?',
            args: [buffer, episode.id],
          });
        }
      } catch (e: any) {
        console.error('Failed to store audio from base64:', e.message);
      }
    }

    return NextResponse.json(
      { ...episode, has_db_audio: !!(audio_path || audio_base64) },
      { status: 201 }
    );
  } catch (error: any) {
    console.error('Failed to create episode:', error);
    return NextResponse.json(
      { error: `创建节目失败: ${error.message || '未知错误'}` },
      { status: 500 }
    );
  }
}

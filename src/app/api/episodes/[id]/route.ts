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

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const result = await db.execute({
      sql: 'SELECT * FROM episodes WHERE id = ?',
      args: [params.id],
    });

    if (result.rows.length === 0) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const row = result.rows[0] as any;
    const episode = {
      ...row,
      audio_data: undefined,
      has_db_audio: !!(row.audio_data),
    };
    return NextResponse.json(episode);
  } catch (error) {
    console.error('Failed to get episode:', error);
    return NextResponse.json(
      { error: 'Failed to get episode' },
      { status: 500 }
    );
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const { audio_base64, ...episodeData } = body;

    await db.execute({
      sql: `UPDATE episodes SET
        episode_number = ?,
        title = ?,
        guest = ?,
        description = ?,
        transcript = ?,
        cover_image = ?,
        duration = ?,
        publish_date = ?,
        link_xiaoyuzhou = ?,
        link_apple_podcasts = ?,
        audio_url = ?,
        updated_at = CURRENT_TIMESTAMP
      WHERE id = ?`,
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
        params.id,
      ],
    });

    // 将 base64 音频数据解码存入 BLOB 列
    await storeAudioFromBase64(Number(params.id), audio_base64 || null);

    const updated = await db.execute({
      sql: 'SELECT * FROM episodes WHERE id = ?',
      args: [params.id],
    });

    const episode = updated.rows[0] as unknown as Episode;
    return NextResponse.json(episode);
  } catch (error) {
    console.error('Failed to update episode:', error);
    return NextResponse.json(
      { error: 'Failed to update episode' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    await db.execute({
      sql: 'DELETE FROM episodes WHERE id = ?',
      args: [params.id],
    });
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Failed to delete episode:', error);
    return NextResponse.json(
      { error: 'Failed to delete episode' },
      { status: 500 }
    );
  }
}

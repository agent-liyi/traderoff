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

    const episode = result.rows[0] as unknown as Episode;
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
        params.id,
      ],
    });

    // 将本地音频文件存入 BLOB 列
    await storeAudioBlob(Number(params.id), body.audio_url || null);

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

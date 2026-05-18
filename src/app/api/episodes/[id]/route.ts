import { NextRequest, NextResponse } from 'next/server';
import db from '@/lib/db';
import { Episode } from '@/lib/types';

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

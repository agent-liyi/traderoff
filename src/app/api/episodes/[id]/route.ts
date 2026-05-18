import { NextRequest, NextResponse } from 'next/server';
import getDb from '@/lib/db';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const db = getDb();
    const episode = db
      .prepare('SELECT * FROM episodes WHERE id = ?')
      .get(params.id);

    if (!episode) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

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
    const db = getDb();

    const stmt = db.prepare(`
      UPDATE episodes SET
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
      WHERE id = ?
    `);

    stmt.run(
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
      params.id
    );

    const episode = db
      .prepare('SELECT * FROM episodes WHERE id = ?')
      .get(params.id);

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
    const db = getDb();
    db.prepare('DELETE FROM episodes WHERE id = ?').run(params.id);
    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Failed to delete episode:', error);
    return NextResponse.json(
      { error: 'Failed to delete episode' },
      { status: 500 }
    );
  }
}

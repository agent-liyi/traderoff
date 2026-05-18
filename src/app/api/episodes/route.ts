import { NextRequest, NextResponse } from 'next/server';
import getDb from '@/lib/db';

export async function GET() {
  try {
    const db = getDb();
    const episodes = db
      .prepare('SELECT * FROM episodes ORDER BY id DESC')
      .all();
    return NextResponse.json(episodes);
  } catch (error) {
    console.error('Failed to get episodes:', error);
    return NextResponse.json([], { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const db = getDb();

    const stmt = db.prepare(`
      INSERT INTO episodes (episode_number, title, guest, description, transcript, cover_image, duration, publish_date, link_xiaoyuzhou, link_apple_podcasts, audio_url)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const result = stmt.run(
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
      body.audio_url || null
    );

    const episode = db
      .prepare('SELECT * FROM episodes WHERE id = ?')
      .get(result.lastInsertRowid);

    return NextResponse.json(episode, { status: 201 });
  } catch (error) {
    console.error('Failed to create episode:', error);
    return NextResponse.json(
      { error: 'Failed to create episode' },
      { status: 500 }
    );
  }
}

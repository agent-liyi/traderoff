import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';

const UPLOAD_DIR = '/tmp/uploads';

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const filePath = path.join(UPLOAD_DIR, ...params.path);

  // 安全检查：不允许路径穿越
  if (!filePath.startsWith(UPLOAD_DIR)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  if (!existsSync(filePath)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const ext = path.extname(filePath).toLowerCase();
  const mimeMap: Record<string, string> = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
  };

  const contentType = mimeMap[ext] || 'application/octet-stream';
  const buffer = await readFile(filePath);

  return new NextResponse(buffer, {
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=31536000, immutable',
    },
  });
}

import { NextRequest, NextResponse } from 'next/server';
import { mkdir } from 'fs/promises';
import { createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';
import path from 'path';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    // Generate unique filename
    const ext = path.extname(file.name);
    const filename = `${Date.now()}-${Math.random().toString(36).substring(2, 8)}${ext}`;
    const uploadDir = path.join(process.cwd(), 'public', 'uploads');

    // 确保上传目录存在
    await mkdir(uploadDir, { recursive: true });

    const filePath = path.join(uploadDir, filename);

    // 流式写入，不把整个文件加载到内存
    const readable = Readable.fromWeb(file.stream() as any);
    await pipeline(readable, createWriteStream(filePath));

    return NextResponse.json({ url: `/uploads/${filename}` });
  } catch (error) {
    console.error('Upload failed:', error);
    return NextResponse.json({ error: 'Upload failed' }, { status: 500 });
  }
}

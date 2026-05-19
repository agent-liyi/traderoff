import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';
import fs from 'fs';

const UPLOAD_DIR = '/tmp/uploads';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ error: '未选择文件' }, { status: 400 });
    }

    // 创建上传目录
    await mkdir(UPLOAD_DIR, { recursive: true });

    const ext = path.extname(file.name) || '';
    const safeName = `${Date.now()}-${Math.random().toString(36).slice(2)}${ext}`;
    const filePath = path.join(UPLOAD_DIR, safeName);

    // 流式写入，不占内存
    const bytes = new Uint8Array(await file.arrayBuffer());
    await writeFile(filePath, bytes);

    // 格式验证
    const acceptedAudio = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/aac', 'audio/mp4', 'audio/x-m4a'];
    const acceptedImage = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/svg+xml'];

    if (!acceptedAudio.includes(file.type) && !acceptedImage.includes(file.type)) {
      // 清理无效文件
      try { fs.unlinkSync(filePath); } catch {}
      return NextResponse.json({
        error: `不支持的文件类型: ${file.type}。支持的音频: MP3/WAV/OGG/AAC/M4A，支持的图片: PNG/JPEG/WebP/GIF`
      }, { status: 400 });
    }

    return NextResponse.json({
      path: filePath,
      filename: file.name,
      size: file.size,
      mimeType: file.type,
    });
  } catch (error: any) {
    console.error('Upload failed:', error);
    return NextResponse.json({
      error: `上传失败: ${error.message || '未知错误'}`
    }, { status: 500 });
  }
}

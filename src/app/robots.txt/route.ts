import { NextResponse } from 'next/server';
import { headers } from 'next/headers';

export const dynamic = 'force-dynamic';

export async function GET() {
  const headersList = headers();
  const host = headersList.get('host') ?? 'dongtaipingheng.com';
  const protocol = host.includes('localhost') ? 'http' : 'https';
  const baseUrl = `${protocol}://${host}`;

  const body = `# robots.txt — 动态平衡播客
# https://www.robotstxt.org/

User-agent: *
Allow: /
Disallow: /admin
Disallow: /api/

# AI search crawlers — explicitly allowed
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: Amazonbot
Allow: /

# Sitemap
Sitemap: ${baseUrl}/sitemap.xml

# llms.txt — AI content index
# ${baseUrl}/llms.txt
# ${baseUrl}/llms-full.txt
`;

  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=86400',
    },
  });
}

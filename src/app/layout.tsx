import type { Metadata } from 'next';
import './globals.css';
import PlayerShell from '@/components/PlayerShell';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://dongtaipingheng.com';

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: '动态平衡 — 播客',
    template: '%s · 动态平衡',
  },
  description:
    '在变化中寻找平衡，在对话中发现可能。每期邀请一位嘉宾，聊聊他们如何在快速变化的世界中，找到属于自己的节奏与平衡。',
  openGraph: {
    siteName: '动态平衡',
    type: 'website',
    locale: 'zh_CN',
    url: BASE_URL,
  },
  twitter: {
    card: 'summary_large_image',
    site: '@dongtaipingheng',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
  alternates: {
    canonical: BASE_URL,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="bg-background text-foreground font-sans antialiased">
        <PlayerShell>
          <div className="pb-player">{children}</div>
        </PlayerShell>
      </body>
    </html>
  );
}

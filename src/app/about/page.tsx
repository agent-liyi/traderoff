import Link from 'next/link';
import type { Metadata } from 'next';

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? 'https://dongtaipingheng.com';

export const metadata: Metadata = {
  title: '关于',
  description:
    '「动态平衡」是一档关注个人成长与生活方式的对话播客，每期邀请一位嘉宾，聊聊他们在快速变化世界中找到节奏与平衡的故事。',
  openGraph: {
    title: '关于 · 动态平衡',
    description:
      '「动态平衡」是一档关注个人成长与生活方式的对话播客，每期邀请一位嘉宾，聊聊他们在快速变化世界中找到节奏与平衡的故事。',
    url: `${BASE_URL}/about`,
    type: 'website',
    locale: 'zh_CN',
    siteName: '动态平衡',
  },
  alternates: {
    canonical: `${BASE_URL}/about`,
  },
};

export default function AboutPage() {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-stone-200">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between">
          <Link href="/" className="text-lg sm:text-xl font-bold tracking-tight">
            动态平衡
          </Link>
          <nav className="flex gap-4 sm:gap-6 text-sm text-muted">
            <Link href="/" className="hover:text-foreground transition-colors">
              首页
            </Link>
            <Link href="/episodes" className="hover:text-foreground transition-colors">
              节目
            </Link>
            <Link href="/about" className="text-foreground font-medium">
              关于
            </Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-16">
        <h1 className="text-3xl md:text-4xl font-bold mb-8">关于动态平衡</h1>

        <section className="mb-12">
          <h2 className="text-xl font-bold mb-4">关于播客</h2>
          <div className="space-y-4 text-foreground leading-relaxed">
            <p>
              「动态平衡」是一档关注个人成长与生活方式的对话播客。我们相信，平衡不是一个静止的状态，
              而是一种持续调整的能力——在工作与生活之间、理性与感性之间、独处与社交之间，
              找到属于当下的最优解。
            </p>
            <p>
              每期节目，我们邀请一位在某个领域有深度思考的嘉宾，聊聊他们的经历、困惑与发现。
              不追求标准答案，只希望每次对话都能打开一个新的视角。
            </p>
            <p>
              节目每两周更新一期，你可以在小宇宙、苹果播客、Spotify 等平台收听。
            </p>
          </div>
        </section>

        <section className="mb-12">
          <h2 className="text-xl font-bold mb-4">主播</h2>
          <div className="space-y-4 text-foreground leading-relaxed">
            <p>
              <strong>李逸</strong> — 产品设计师，对人如何做决定这件事有持续的好奇。
              相信好的对话能让人看见自己的盲区。工作之余喜欢跑步、阅读和做饭。
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-bold mb-4">联系我们</h2>
          <p className="text-foreground leading-relaxed">
            合作、推荐嘉宾或只是想聊聊，都欢迎发邮件到{' '}
            <a
              href="mailto:hello@dongtaipingheng.com"
              className="text-accent hover:underline"
              rel="noopener noreferrer"
            >
              hello@dongtaipingheng.com
            </a>
          </p>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-stone-200">
        <div className="max-w-5xl mx-auto px-6 py-8 text-center text-sm text-muted">
          <p>© 2026 动态平衡播客. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

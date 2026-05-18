'use client';

import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Placeholder from '@tiptap/extension-placeholder';
import { useEffect } from 'react';

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

export default function RichTextEditor({
  content,
  onChange,
  placeholder = '开始编辑...',
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Link.configure({
        openOnClick: false,
      }),
      Image,
      Placeholder.configure({
        placeholder,
      }),
    ],
    content,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: 'tiptap prose max-w-none focus:outline-none',
      },
    },
  });

  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content);
    }
  }, [content, editor]);

  if (!editor) return null;

  const addLink = () => {
    const url = prompt('输入链接 URL:');
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  };

  const addImage = () => {
    const url = prompt('输入图片 URL:');
    if (url) {
      editor.chain().focus().setImage({ src: url }).run();
    }
  };

  return (
    <div className="border border-stone-300 rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-1 p-2 border-b border-stone-200 bg-stone-50">
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('bold')
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          B
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`px-2 py-1 text-xs rounded italic ${
            editor.isActive('italic')
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          I
        </button>
        <button
          type="button"
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 2 }).run()
          }
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('heading', { level: 2 })
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          H2
        </button>
        <button
          type="button"
          onClick={() =>
            editor.chain().focus().toggleHeading({ level: 3 }).run()
          }
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('heading', { level: 3 })
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          H3
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('bulletList')
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          列表
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('orderedList')
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          有序
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          className={`px-2 py-1 text-xs rounded ${
            editor.isActive('blockquote')
              ? 'bg-accent text-white'
              : 'hover:bg-stone-200'
          }`}
        >
          引用
        </button>
        <button
          type="button"
          onClick={addLink}
          className="px-2 py-1 text-xs rounded hover:bg-stone-200"
        >
          链接
        </button>
        <button
          type="button"
          onClick={addImage}
          className="px-2 py-1 text-xs rounded hover:bg-stone-200"
        >
          图片
        </button>
      </div>

      {/* Editor */}
      <div className="p-4 min-h-[200px]">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

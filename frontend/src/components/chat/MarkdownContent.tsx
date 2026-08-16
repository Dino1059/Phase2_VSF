import React, { useMemo } from 'react';
import { marked } from 'marked';

interface MarkdownContentProps {
  content: string;
  className?: string;
}

// Configure marked with GitHub Flavored Markdown and breaks
marked.setOptions({
  gfm: true,
  breaks: true,
});

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, className = '' }) => {
  const html = useMemo(() => {
    if (!content) return '';
    try {
      // Parse markdown to HTML
      const parsed = marked.parse(content, { async: false }) as string;
      return parsed;
    } catch {
      return content;
    }
  }, [content]);

  return (
    <div
      className={`markdown-body ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
};

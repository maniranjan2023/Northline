import type { Components } from 'react-markdown'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

const markdownComponents: Components = {
  h1: ({ children }) => <h1 className="mb-3 mt-4 text-xl font-bold tracking-tight first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-4 text-lg font-semibold tracking-tight first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-2 mt-3 text-base font-semibold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mb-1 mt-2 text-sm font-semibold">{children}</h4>,
  p: ({ children }) => <p className="mb-2 text-sm leading-relaxed last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 ml-4 list-disc space-y-1 text-sm">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 ml-4 list-decimal space-y-1 text-sm">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-primary/40 pl-3 text-sm italic text-muted-foreground">{children}</blockquote>
  ),
  hr: () => <hr className="my-4 border-border" />,
  a: ({ href, children }) => (
    <a href={href} className="font-medium text-primary underline-offset-2 hover:underline" target="_blank" rel="noreferrer">
      {children}
    </a>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes('language-')
    if (isBlock) {
      return (
        <pre className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-xs">
          <code>{children}</code>
        </pre>
      )
    }
    return <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">{children}</code>
  },
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b bg-muted/50">{children}</thead>,
  th: ({ children }) => <th className="px-3 py-2 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border-t px-3 py-2 align-top">{children}</td>,
}

interface Props {
  content: string
  className?: string
}

export function MarkdownContent({ content, className }: Props) {
  return (
    <div className={cn('text-foreground', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

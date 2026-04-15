
import { MarkdownRenderer } from '@/lib/markdown-renderer';
import { Button } from '@/components/ui/Button';

interface AgentResponseProps {
  content: string;
  isStreaming?: boolean;
  onCreatePlan?: () => void;
}

export function AgentResponse({ content, isStreaming, onCreatePlan }: AgentResponseProps) {
  return (
    <div className="flex flex-col gap-2 relative group max-w-full">
      <div 
        className="rounded-xl px-4 py-3 text-sm"
        style={{
          background: 'var(--color-surface-hover)',
          color: 'var(--color-text-main)',
          border: '1px solid var(--color-border)',
          borderBottomLeftRadius: '4px'
        }}
      >
        <div className="prose prose-invert max-w-none text-sm
          prose-p:leading-relaxed prose-pre:bg-[var(--color-surface)] prose-pre:border prose-pre:border-[var(--color-border)]
          prose-a:text-[var(--color-primary)] hover:prose-a:text-[var(--color-primary-hover)]
          prose-headings:text-[var(--color-text-main)] prose-strong:text-[var(--color-text-main)]
          prose-code:text-[var(--color-primary-muted)] prose-code:bg-[var(--color-surface)] prose-code:px-1 prose-code:py-0.5 prose-code:rounded
        ">
          <MarkdownRenderer content={content} />
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 ml-1 bg-[var(--color-primary)] animate-pulse align-middle" />
          )}
        </div>
      </div>
      
      {/* Inline action: create plan from this response */}
      {!isStreaming && onCreatePlan && (
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity px-1">
          <Button size="sm" variant="secondary" className="h-6 text-[10px] px-2" onClick={onCreatePlan}>
            <span className="material-symbols-outlined text-[12px] mr-1">auto_awesome</span>
            Create Plan from here
          </Button>
        </div>
      )}
    </div>
  );
}

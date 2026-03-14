/**
 * ChatMessage — Individual chat bubble for user and assistant messages.
 *
 * User messages: right-aligned, primary color background.
 * Assistant messages: left-aligned, muted background with simple markdown rendering.
 * Timestamp rendered below each bubble as relative time.
 */

import type { ChatMessage as ChatMessageType } from '../../types';

interface ChatMessageProps {
  message: ChatMessageType;
}

/** Render relative time string from a Unix millisecond timestamp. */
function formatRelativeTime(ts: number): string {
  const diffMs = Date.now() - ts;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

/**
 * Minimal markdown renderer: bold (**text**) and unordered list items (- item).
 * Returns an array of React elements so we avoid dangerouslySetInnerHTML.
 */
function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];

  const flushList = (key: string) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key}`} className="list-disc list-inside space-y-0.5 my-1">
          {listItems.map((item, i) => (
            <li key={i} className="text-sm">
              {renderInline(item)}
            </li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  lines.forEach((line, idx) => {
    const listMatch = line.match(/^[-*]\s+(.*)/);
    if (listMatch) {
      listItems.push(listMatch[1]);
    } else {
      flushList(String(idx));
      if (line.trim() === '') {
        elements.push(<br key={`br-${idx}`} />);
      } else {
        elements.push(
          <span key={`line-${idx}`} className="block text-sm leading-relaxed">
            {renderInline(line)}
          </span>,
        );
      }
    }
  });
  flushList('end');

  return <>{elements}</>;
}

/** Render inline bold markers (**text**). */
function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    const boldMatch = part.match(/^\*\*([^*]+)\*\*$/);
    if (boldMatch) {
      return <strong key={i}>{boldMatch[1]}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-3`}>
      <div
        className={
          isUser
            ? 'max-w-[80%] rounded-2xl rounded-br-sm px-3 py-2 bg-primary text-primary-foreground'
            : 'max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 bg-muted text-foreground'
        }
      >
        {isUser ? (
          <p className="text-sm leading-relaxed">{message.content}</p>
        ) : (
          <div>{renderMarkdown(message.content)}</div>
        )}
      </div>
      <span className="text-[10px] text-muted-foreground mt-1 px-1">
        {formatRelativeTime(message.timestamp)}
      </span>
    </div>
  );
}

/**
 * QuickActions — Horizontal scrollable row of suggestion chips.
 *
 * Clicking a chip fires onSelect with the chip text, which the parent
 * can immediately submit as a user message.
 */

interface QuickActionsProps {
  onSelect: (text: string) => void;
}

const SUGGESTIONS = [
  'Is my area safe?',
  'Current flood risk',
  'Evacuation routes',
  'Weather forecast',
];

export function QuickActions({ onSelect }: QuickActionsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar px-1">
      {SUGGESTIONS.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 active:bg-emerald-200 transition-colors whitespace-nowrap"
        >
          {text}
        </button>
      ))}
    </div>
  );
}

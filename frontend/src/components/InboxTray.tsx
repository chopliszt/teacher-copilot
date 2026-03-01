import { useImportantEmails } from '../lib/hooks/useImportantEmails';

function senderLabel(raw: string): string {
  // "Design Cat <noreply@designcat.com>" → "designcat.com"
  const match = raw.match(/@([\w.-]+)/);
  return match ? match[1] : raw.split('<')[0].trim();
}

function timeAgo(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days}d ago`;
}

export function InboxTray() {
  const { data: emails = [], isLoading } = useImportantEmails();

  if (isLoading || emails.length === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-1.5 h-1.5 rounded-full bg-amber-500/60" />
        <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
          Needs action · {emails.length}
        </h2>
      </div>

      <div className="space-y-2">
        {emails.map((email) => (
          <div
            key={email.id}
            className="bg-stone-900 border border-stone-800 rounded-xl px-4 py-3 flex items-start gap-3"
          >
            <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-stone-200 text-sm truncate">{email.subject}</p>
              <p className="text-stone-600 text-xs mt-0.5">
                {senderLabel(email.sender)} · {timeAgo(email.date)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

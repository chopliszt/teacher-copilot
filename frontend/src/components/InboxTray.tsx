import { useImportantEmails, useDismissEmail, useDismissAllEmails, useSyncEmails, useLastSync } from '../lib/hooks/useImportantEmails';

function senderLabel(raw: string): string {
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

function formatSyncLabel(isoDate: string): { label: string; stale: boolean } {
  const date = new Date(isoDate);
  const diffHours = (Date.now() - date.getTime()) / 3_600_000;
  const stale = diffHours > 26;
  const timeStr = date.toLocaleTimeString('es-CR', { hour: '2-digit', minute: '2-digit' });
  const isToday = date.toDateString() === new Date().toDateString();
  const isYesterday = date.toDateString() === new Date(Date.now() - 86_400_000).toDateString();
  const dayStr = isToday ? 'today' : isYesterday ? 'yesterday' : date.toLocaleDateString('en-US', { weekday: 'short' });
  return { label: `synced ${dayStr} at ${timeStr}`, stale };
}

export function InboxTray() {
  const { data: emails = [], isLoading } = useImportantEmails();
  const { data: syncState } = useLastSync();
  const dismiss = useDismissEmail();
  const dismissAll = useDismissAllEmails();
  const sync = useSyncEmails();

  const syncInfo = syncState?.last_sync_at ? formatSyncLabel(syncState.last_sync_at) : null;
  const syncFailed = syncState?.status === 'error';

  return (
    <div className="mb-8">
      {syncFailed && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-xl border border-amber-500/20 bg-amber-500/5">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500/70 flex-shrink-0">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span className="text-amber-500/70 text-xs">
            Gmail auth expired — run <code className="font-mono">python auth_gmail.py</code> in the backend
          </span>
        </div>
      )}

      {!isLoading && emails.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-amber-500/60" />
              <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
                Needs action · {emails.length}
              </h2>
            </div>
            <button
              onClick={() => dismissAll.mutate()}
              disabled={dismissAll.isPending}
              className="text-stone-600 text-xs hover:text-stone-400 transition-colors duration-200 disabled:opacity-40"
            >
              clear all
            </button>
          </div>

          <div className="space-y-2 mb-3">
            {emails.map((email) => (
              <div
                key={email.id}
                className="bg-stone-900 border border-stone-800 rounded-xl px-4 py-3 flex items-start gap-3 group"
              >
                <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-stone-200 text-sm truncate">{email.subject}</p>
                  <p className="text-stone-600 text-xs mt-0.5">
                    {senderLabel(email.sender)} · {timeAgo(email.date)}
                  </p>
                </div>
                <button
                  onClick={() => dismiss.mutate(email.id)}
                  disabled={dismiss.isPending}
                  aria-label="Dismiss"
                  className="flex-shrink-0 opacity-0 group-hover:opacity-100 text-stone-600 hover:text-stone-300 transition-all duration-200 disabled:opacity-40 p-0.5"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <line x1="1" y1="1" x2="13" y2="13" />
                    <line x1="13" y1="1" x2="1" y2="13" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Sync status — always visible */}
      <div className="flex items-center justify-between">
        <span className={`text-xs ${syncFailed || syncInfo?.stale ? 'text-amber-500/60' : 'text-stone-600'}`}>
          {syncFailed ? '· sync error' : syncInfo ? `· ${syncInfo.label}` : '· never synced'}
        </span>
        <button
          onClick={() => sync.mutate()}
          disabled={sync.isPending}
          aria-label="Sync emails"
          className="text-stone-600 hover:text-stone-400 transition-colors duration-200 disabled:opacity-40"
        >
          <svg
            width="13" height="13" viewBox="0 0 13 13" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            className={sync.isPending ? 'animate-spin' : ''}
          >
            <path d="M11.5 2A6 6 0 1 0 12 6.5" />
            <polyline points="11.5 2 11.5 5.5 8 5.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}

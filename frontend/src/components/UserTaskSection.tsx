import { useState } from 'react';
import { useUserTasks, useAddTask, useDeleteTask } from '../lib/hooks/useUserTasks';

export function UserTaskSection() {
  const { data: tasks = [] } = useUserTasks();
  const addTask = useAddTask();
  const deleteTask = useDeleteTask();

  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [dueDate, setDueDate] = useState('');

  const handleAdd = () => {
    if (!title.trim()) return;
    addTask.mutate(
      { title: title.trim(), priority, due_date: dueDate || undefined },
      {
        onSuccess: () => {
          setTitle('');
          setPriority('medium');
          setDueDate('');
          setFormOpen(false);
        },
      },
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleAdd();
    if (e.key === 'Escape') setFormOpen(false);
  };

  const priorityColor = {
    high: 'text-red-400 border-red-500/30 bg-red-500/10',
    medium: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
    low: 'text-stone-500 border-stone-700 bg-stone-800/60',
  };

  return (
    <section className="mt-8">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-stone-600" />
          <h2 className="text-stone-500 text-xs font-semibold tracking-widest uppercase">
            Your tasks{tasks.length > 0 ? ` · ${tasks.length}` : ''}
          </h2>
        </div>
        {!formOpen && (
          <button
            onClick={() => setFormOpen(true)}
            className="text-stone-600 hover:text-stone-400 text-xs border border-stone-800 hover:border-stone-700 px-2.5 py-1 rounded-lg transition-colors"
          >
            + Add task
          </button>
        )}
      </div>

      {/* Inline add form */}
      {formOpen && (
        <div className="mb-3 bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-3">
          <input
            autoFocus
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What do you need to do?"
            className="w-full bg-stone-950 border border-stone-800 rounded-lg px-3 py-2 text-stone-200 text-sm placeholder-stone-700 focus:outline-none focus:border-stone-600"
          />
          <div className="flex gap-2 items-center">
            {/* Priority selector */}
            <div className="flex gap-1">
              {(['high', 'medium', 'low'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPriority(p)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    priority === p
                      ? priorityColor[p]
                      : 'text-stone-600 border-stone-800 hover:border-stone-700'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
            {/* Optional due date */}
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="bg-stone-950 border border-stone-800 rounded-lg px-2 py-1 text-stone-500 text-xs focus:outline-none focus:border-stone-600 ml-auto"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={!title.trim() || addTask.isPending}
              className="flex-1 py-2 rounded-lg bg-stone-700 hover:bg-stone-600 disabled:opacity-40 disabled:cursor-not-allowed text-stone-200 text-xs font-medium transition-all"
            >
              {addTask.isPending ? 'Adding…' : 'Add'}
            </button>
            <button
              onClick={() => { setFormOpen(false); setTitle(''); }}
              className="px-4 py-2 rounded-lg border border-stone-800 hover:border-stone-700 text-stone-600 hover:text-stone-400 text-xs transition-all"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Task list */}
      {tasks.length === 0 && !formOpen ? (
        <p className="text-stone-700 text-xs italic">
          No tasks added yet. Tap "+ Add task" to throw something into the mix.
        </p>
      ) : (
        <div className="space-y-1.5">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="flex items-center gap-3 bg-stone-900/60 border border-stone-800/60 rounded-xl px-3 py-2.5"
            >
              <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full border ${priorityColor[task.priority]}`}>
                {task.priority}
              </span>
              <span className="text-stone-300 text-sm flex-1 min-w-0 truncate">{task.title}</span>
              {task.due_date && (
                <span className="text-stone-600 text-xs flex-shrink-0">{task.due_date}</span>
              )}
              <button
                onClick={() => deleteTask.mutate(task.id)}
                className="text-stone-700 hover:text-stone-500 text-xs flex-shrink-0 transition-colors"
                aria-label="Remove task"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

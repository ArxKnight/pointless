import { useState } from 'react';
import { User } from '../types/api';
import { post } from '../lib/api';

export function Settings({ user }: { user: User }) {
  const [regen, setRegen] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [regenMsg, setRegenMsg] = useState('');

  async function handleRegenerate() {
    if (!confirm('This will delete and regenerate all giving assignments for the current quarter. Any points already marked as sent will block this action. Continue?')) return;
    setRegen('loading');
    try {
      const res = await post<{ quarter: { label: string }; plans: unknown[] }>('/quarters/regenerate');
      setRegenMsg(`Done — ${res.quarter.label} regenerated with ${(res.plans as unknown[]).length} new assignments.`);
      setRegen('done');
    } catch (e: any) {
      setRegenMsg(e.message || 'Regeneration failed.');
      setRegen('error');
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Settings</h1>
        <p className="mt-1 text-slate-400">Account and system settings.</p>
      </div>

      {/* Account info */}
      <div className="card p-6 space-y-3">
        <h2 className="text-lg font-semibold">Your Account</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-sm">
          <div>
            <p className="text-slate-400">Display name</p>
            <p className="mt-0.5 font-medium">{user.display_name}</p>
          </div>
          <div>
            <p className="text-slate-400">Username</p>
            <p className="mt-0.5 font-medium">{user.username}</p>
          </div>
          <div>
            <p className="text-slate-400">Email</p>
            <p className="mt-0.5 font-medium">{user.email}</p>
          </div>
          <div>
            <p className="text-slate-400">Role</p>
            <p className="mt-0.5 font-medium">{user.is_admin ? '🔑 Administrator' : 'Member'}</p>
          </div>
        </div>
      </div>

      {/* Admin-only: regenerate quarter */}
      {user.is_admin && (
        <div className="card p-6 space-y-4 border border-yellow-500/20">
          <div>
            <h2 className="text-lg font-semibold">Regenerate Current Quarter</h2>
            <p className="mt-1 text-sm text-slate-400">
              Use this if the quarter assignments need to be rebuilt — for example after members were added or removed.
              All existing assignments for the current quarter will be wiped and regenerated.
              This is blocked once any points have been marked as sent.
            </p>
          </div>

          {regenMsg && (
            <p className={`rounded-lg p-3 text-sm ${regen === 'error' ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400'}`}>
              {regenMsg}
            </p>
          )}

          <button
            onClick={handleRegenerate}
            disabled={regen === 'loading'}
            className="rounded-xl bg-yellow-500 px-5 py-2.5 text-sm font-semibold text-black hover:bg-yellow-400 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {regen === 'loading' ? 'Regenerating…' : '⟳ Regenerate Quarter'}
          </button>
        </div>
      )}
    </div>
  );
}

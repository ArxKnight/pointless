import {FormEvent, useEffect, useMemo, useState} from 'react';
import {post} from '../lib/api';

type Db = {host: string; port: number; database: string; username: string; password: string};
type AdminFields = {username: string; password: string; display_name: string; email: string};
type Probe = {
  success: boolean; connected: boolean;
  database_exists?: boolean; points_schema_detected?: boolean;
  missing_tables?: string[];
  existing_admin?: {username: string; email: string; display_name: string} | null;
  error?: string;
};

const defaultDb: Db = {host: 'mysql', port: 3306, database: 'pointsdb', username: 'pointsapp', password: 'points_password_change_me'};
const defaultAdmin: AdminFields = {username: 'admin', password: '', display_name: 'Administrator', email: 'admin@example.com'};

function Field({label, type='text', value, onChange, placeholder}: {label:string; type?:string; value:string|number; onChange:(v:string)=>void; placeholder?:string}) {
  return (
    <label className="block text-sm">
      {label}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-2 w-full rounded-lg border border-border bg-bg p-3"
      />
    </label>
  );
}

export function Install({onInstalled}: {onInstalled: () => void}) {
  const [step, setStep] = useState<1 | 2>(1);
  const [db, setDb] = useState<Db>(defaultDb);
  const [admin, setAdmin] = useState<AdminFields>(defaultAdmin);
  const [probe, setProbe] = useState<Probe | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);

  // Probe result drives whether step 2 needs admin creation or can reuse
  const canReuse = useMemo(
    () => Boolean(probe?.connected && probe.database_exists && probe.points_schema_detected && probe.existing_admin),
    [probe]
  );

  // Reset probe when DB fields change
  useEffect(() => { setProbe(null); setErr(''); }, [db.host, db.port, db.database, db.username, db.password]);

  // Auto-redirect after success
  useEffect(() => {
    if (!success) return;
    const t = window.setTimeout(onInstalled, 3000);
    return () => window.clearTimeout(t);
  }, [success, onInstalled]);

  async function testConnection() {
    setBusy(true); setErr('');
    try {
      const result = await post<Probe>('/install/test-connection', {database: db});
      setProbe(result);
      if (!result.connected || !result.success) setErr(result.error || 'Connection failed');
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleStep1Next(e: FormEvent) {
    e.preventDefault();
    if (!probe?.connected) { await testConnection(); return; }
    setErr(''); setStep(2);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr('');
    try {
      await post('/install/setup', canReuse
        ? {database: db, reuse_existing_database: true}
        : {database: db, reuse_existing_database: false, admin}
      );
      setSuccess(true);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (success) return (
    <div className="min-h-screen bg-bg p-4">
      <div className="mx-auto flex min-h-[80vh] max-w-xl items-center justify-center">
        <div className="card glow p-8 text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20 text-3xl text-green-300">✓</div>
          <h1 className="text-3xl font-bold tracking-tight">Install complete</h1>
          <p className="mt-3 text-slate-300">Pointless is ready. Your first quarter plan has been generated automatically.</p>
          <p className="mt-2 text-sm text-slate-500">Redirecting to login…</p>
          <button onClick={onInstalled} className="mt-6 rounded-lg bg-indigo-500 px-5 py-3 font-semibold">Go to login now</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-bg p-4">
      <div className="mx-auto max-w-2xl py-10">
        <div className="card glow p-8">
          <h1 className="text-3xl font-bold tracking-tight">First-run setup</h1>
          <p className="mt-2 text-slate-400 text-sm">
            Connect to MySQL and create the first administrator. Your first quarter plan will be generated automatically once setup is complete.
          </p>

          {/* Step indicator */}
          <div className="mt-6 flex items-center gap-3">
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${step === 1 ? 'bg-indigo-500 text-white' : 'bg-green-600 text-white'}`}>
              {step === 1 ? '1' : '✓'}
            </div>
            <span className={`text-sm font-medium ${step === 1 ? 'text-indigo-200' : 'text-slate-400'}`}>Database connection</span>
            <div className="h-px flex-1 bg-border"/>
            <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${step === 2 ? 'bg-indigo-500 text-white' : 'bg-black/30 text-slate-500'}`}>2</div>
            <span className={`text-sm font-medium ${step === 2 ? 'text-indigo-200' : 'text-slate-500'}`}>Admin account</span>
          </div>

          {/* ── STEP 1: Database ── */}
          {step === 1 && (
            <form onSubmit={handleStep1Next} className="mt-8 space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Host" value={db.host} onChange={v => setDb({...db, host: v})}/>
                <Field label="Port" type="number" value={db.port} onChange={v => setDb({...db, port: Number(v)})}/>
                <Field label="Database" value={db.database} onChange={v => setDb({...db, database: v})}/>
                <Field label="Username" value={db.username} onChange={v => setDb({...db, username: v})}/>
                <label className="block text-sm md:col-span-2">
                  Password
                  <input
                    type="password"
                    value={db.password}
                    onChange={e => setDb({...db, password: e.target.value})}
                    className="mt-2 w-full rounded-lg border border-border bg-bg p-3"
                  />
                </label>
              </div>

              {/* Test connection button */}
              <button
                type="button"
                onClick={testConnection}
                disabled={busy}
                className="rounded-lg border border-indigo-500 px-4 py-2 text-indigo-200 disabled:opacity-60"
              >
                {busy ? 'Testing…' : 'Test connection'}
              </button>

              {/* Probe result */}
              {probe?.connected && (
                <div className="rounded-lg border border-green-500/30 bg-green-500/10 p-4 text-sm text-green-200 space-y-1">
                  <p className="font-medium">✓ Connection successful</p>
                  <p>Database exists: {probe.database_exists ? 'yes' : 'no'}</p>
                  {probe.database_exists && <p>Schema detected: {probe.points_schema_detected ? 'yes — existing install found' : 'no — fresh database'}</p>}
                  {canReuse && probe.existing_admin && (
                    <p>Existing admin: <span className="font-mono">{probe.existing_admin.username}</span> ({probe.existing_admin.email}) — will be reused on the next step.</p>
                  )}
                </div>
              )}

              {err && <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={busy || !probe?.connected}
                  className="rounded-lg bg-indigo-500 px-6 py-2.5 font-semibold disabled:bg-slate-700 disabled:cursor-not-allowed"
                >
                  Next →
                </button>
              </div>
            </form>
          )}

          {/* ── STEP 2: Admin account ── */}
          {step === 2 && (
            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              {canReuse ? (
                <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4 text-sm text-indigo-200 space-y-1">
                  <p className="font-medium">Existing database detected</p>
                  <p>An existing Pointless database was found with an admin account already set up. No new admin creation is needed — we'll reconnect to the existing data.</p>
                  {probe?.existing_admin && (
                    <p className="mt-1">Admin: <span className="font-mono">{probe.existing_admin.display_name}</span> ({probe.existing_admin.email})</p>
                  )}
                </div>
              ) : (
                <>
                  <p className="text-slate-400 text-sm">Create the administrator account for this installation.</p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Display name" value={admin.display_name} onChange={v => setAdmin({...admin, display_name: v})}/>
                    <Field label="Email" type="email" value={admin.email} onChange={v => setAdmin({...admin, email: v})}/>
                    <Field label="Username" value={admin.username} onChange={v => setAdmin({...admin, username: v})}/>
                    <Field label="Password" type="password" value={admin.password} onChange={v => setAdmin({...admin, password: v})} placeholder="Min 8 characters"/>
                  </div>
                </>
              )}

              {err && <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{err}</p>}

              <div className="flex justify-between pt-2">
                <button
                  type="button"
                  onClick={() => { setStep(1); setErr(''); }}
                  className="rounded-lg border border-border px-5 py-2.5 text-sm text-slate-300 hover:bg-white/5"
                >
                  ← Back
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-lg bg-indigo-500 px-6 py-2.5 font-semibold disabled:bg-slate-700"
                >
                  {busy ? 'Installing…' : 'Finish setup'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

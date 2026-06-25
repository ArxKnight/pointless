import { useEffect, useState, useCallback } from 'react';
import ReactFlow, {
  Background, Controls, MiniMap,
  MarkerType, Node, Edge, useNodesState, useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../lib/api';
import { Plan, Quarter } from '../types/api';

type OverviewData = {
  quarter: Quarter | null;
  plans: Plan[];
  members: { id: number; display_name: string }[];
};

// Compute who receives what totals per member
function receivedTotals(plans: Plan[]): Map<number, number> {
  const m = new Map<number, number>();
  for (const p of plans) m.set(p.to_member_id, (m.get(p.to_member_id) ?? 0) + p.amount);
  return m;
}

function givingTotals(plans: Plan[]): Map<number, number> {
  const m = new Map<number, number>();
  for (const p of plans) m.set(p.from_member_id, (m.get(p.from_member_id) ?? 0) + p.amount);
  return m;
}

// Lay members out in a circle
function circleLayout(members: { id: number; display_name: string }[], radius = 280): Map<number, { x: number; y: number }> {
  const cx = 360, cy = 300;
  const map = new Map<number, { x: number; y: number }>();
  members.forEach((m, i) => {
    const angle = (2 * Math.PI * i) / members.length - Math.PI / 2;
    map.set(m.id, { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) });
  });
  return map;
}

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState('');
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  const build = useCallback((d: OverviewData) => {
    if (!d.plans.length || !d.members.length) { setNodes([]); setEdges([]); return; }
    const pos = circleLayout(d.members);
    const received = receivedTotals(d.plans);
    const giving = givingTotals(d.plans);

    const newNodes: Node[] = d.members.map(m => {
      const p = pos.get(m.id) ?? { x: 0, y: 0 };
      const recv = received.get(m.id) ?? 0;
      const give = giving.get(m.id) ?? 0;
      return {
        id: `m-${m.id}`,
        position: p,
        data: {
          label: (
            <div style={{ textAlign: 'center', minWidth: 110 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#f1f5f9' }}>{m.display_name}</div>
              <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>
                gives {give} · gets {recv}
              </div>
              <div style={{ fontSize: 10, color: recv >= 50 ? '#22c55e' : '#f59e0b', marginTop: 1 }}>
                {recv >= 50 ? '✓ 50 pts' : `${recv}/50 pts`}
              </div>
            </div>
          ),
        },
        style: {
          background: '#1e2337',
          border: `2px solid ${recv >= 50 ? '#6366f1' : '#f59e0b'}`,
          borderRadius: 14,
          padding: '10px 14px',
          color: '#f1f5f9',
        },
      };
    });

    // Aggregate parallel edges into one (A→B with total amount)
    const edgeMap = new Map<string, { amount: number; allAck: boolean }>();
    for (const p of d.plans) {
      const key = `${p.from_member_id}→${p.to_member_id}`;
      const prev = edgeMap.get(key) ?? { amount: 0, allAck: true };
      edgeMap.set(key, { amount: prev.amount + p.amount, allAck: prev.allAck && p.acknowledged });
    }

    const newEdges: Edge[] = Array.from(edgeMap.entries()).map(([key, val]) => {
      const [fromId, toId] = key.split('→').map(Number);
      return {
        id: `e-${key}`,
        source: `m-${fromId}`,
        target: `m-${toId}`,
        label: `${val.amount} pts`,
        labelStyle: { fill: '#cbd5e1', fontSize: 11 },
        labelBgStyle: { fill: '#0d1117', fillOpacity: 0.85 },
        animated: !val.allAck,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: val.allAck ? '#22c55e' : '#6366f1', strokeWidth: 2 },
      };
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [setNodes, setEdges]);

  useEffect(() => {
    api<OverviewData>('/quarters/active')
      .then(d => { setData(d); build(d); })
      .catch(e => setError(e.message));
  }, [build]);

  if (error) return <div className="card p-6 text-red-400">{error}</div>;
  if (!data) return <div className="card p-6 text-slate-400">Loading overview…</div>;
  if (!data.quarter) return (
    <div className="card p-6 text-slate-400">
      No active quarter yet — one will be generated automatically once there are at least 2 members.
    </div>
  );

  const received = receivedTotals(data.plans);
  const giving = givingTotals(data.plans);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Quarter Overview</h1>
        <p className="mt-1 text-slate-400">
          {data.quarter.label} — full giving tree showing who sends what to who, and that everyone ends up with 50 points.
        </p>
      </div>

      {/* Flow diagram */}
      <div className="h-[520px] overflow-hidden rounded-2xl border border-border bg-[#0d0f1a]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.25 }}
        >
          <Background color="#2a2d3e" />
          <MiniMap
            nodeColor={() => '#6366f1'}
            style={{ background: '#0d0f1a', border: '1px solid #2a2d3e' }}
          />
          <Controls />
        </ReactFlow>
      </div>

      {/* Per-member summary table */}
      <div className="card overflow-hidden">
        <div className="border-b border-border px-6 py-4">
          <h2 className="text-lg font-semibold">Points breakdown</h2>
          <p className="text-sm text-slate-400">Each member gives exactly 50 pts and receives exactly 50 pts.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-slate-400">
                <th className="px-6 py-3 font-medium">Member</th>
                <th className="px-6 py-3 font-medium text-right">Giving</th>
                <th className="px-6 py-3 font-medium text-right">Receiving</th>
                <th className="px-6 py-3 font-medium">Recipients</th>
                <th className="px-6 py-3 font-medium">Givers</th>
                <th className="px-6 py-3 font-medium text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map(m => {
                const outPlans = data.plans.filter(p => p.from_member_id === m.id);
                const inPlans = data.plans.filter(p => p.to_member_id === m.id);
                const totalGive = giving.get(m.id) ?? 0;
                const totalRecv = received.get(m.id) ?? 0;
                const balanced = totalGive === 50 && totalRecv === 50;
                return (
                  <tr key={m.id} className="border-b border-border/40 hover:bg-white/5">
                    <td className="px-6 py-3 font-medium">{m.display_name}</td>
                    <td className="px-6 py-3 text-right text-yellow-400">{totalGive}</td>
                    <td className="px-6 py-3 text-right text-indigo-400">{totalRecv}</td>
                    <td className="px-6 py-3 text-slate-300 text-xs">
                      {outPlans.map(p => `${p.to_name} (${p.amount})`).join(', ')}
                    </td>
                    <td className="px-6 py-3 text-slate-300 text-xs">
                      {inPlans.map(p => `${p.from_name} (${p.amount})`).join(', ')}
                    </td>
                    <td className="px-6 py-3 text-center">
                      {balanced
                        ? <span className="rounded-full bg-green-500/10 px-2 py-0.5 text-xs text-green-400">✓ Balanced</span>
                        : <span className="rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs text-yellow-400">Pending</span>
                      }
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

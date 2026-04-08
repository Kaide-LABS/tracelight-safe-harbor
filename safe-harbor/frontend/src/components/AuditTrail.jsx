import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function AuditTrail({ jobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/audit/${jobId}`)
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      });
  }, [jobId]);

  if (loading) return <div className="text-center p-4">Loading audit trail...</div>;
  if (!data) return null;

  // Deduplicate audit log entries (same phase+detail = keep last)
  const seen = new Map();
  (data.audit_log || []).forEach(log => {
    const key = `${log.phase}|${log.detail}`;
    seen.set(key, log);
  });
  const dedupedLog = [...seen.values()];

  const genMeta = data.synthetic_payload?.generation_metadata;
  const costEntries = data.cost_entries || [];

  return (
    <div className="bg-[#0D1117] border border-[#30363D] rounded overflow-hidden text-sm">
      <div className="bg-[#161B22] p-3 border-b border-[#30363D] font-bold">
        CTO Audit Trail
      </div>
      <div className="p-4 space-y-6 max-h-[600px] overflow-y-auto">

        {/* Phase Timings */}
        <div>
          <h3 className="font-bold mb-2 text-[#4ADE80]">Phase Timings</h3>
          <table className="w-full text-left">
            <tbody>
              {dedupedLog.filter(l => l.detail.includes("successful") || l.detail.includes("parsed")).map((log, i) => (
                <tr key={i} className="border-b border-[#30363D]">
                  <td className="py-1 opacity-70">{log.phase}</td>
                  <td className="py-1">{log.detail}</td>
                  <td className="py-1 text-xs opacity-50">{log.agent && `(${log.agent})`}</td>
                  <td className="py-1 font-mono text-xs">{new Date(log.timestamp).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Plug Adjustments */}
        {data.validation_result?.adjustments?.length > 0 && (
          <div>
            <h3 className="font-bold mb-2 text-[#FBBF24]">Plug Adjustments</h3>
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[#30363D]">
                  <th className="py-1">Target</th>
                  <th className="py-1">Period</th>
                  <th className="py-1">Original</th>
                  <th className="py-1">Adjusted</th>
                  <th className="py-1">Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.validation_result.adjustments.map((adj, i) => (
                  <tr key={i} className="border-b border-[#30363D]">
                    <td className="py-1">{adj.target_cell}</td>
                    <td className="py-1">{adj.period}</td>
                    <td className="py-1 font-mono">{adj.original_value.toLocaleString()}</td>
                    <td className="py-1 font-mono text-[#FBBF24]">{adj.adjusted_value.toLocaleString()}</td>
                    <td className="py-1 text-xs">{adj.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Model Pipeline */}
        <div>
          <h3 className="font-bold mb-2 text-[#4ADE80]">Model Pipeline</h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[#30363D] text-xs opacity-50">
                <th className="py-1">Step</th>
                <th className="py-1">Model</th>
                <th className="py-1">Tokens</th>
                <th className="py-1">Cost</th>
              </tr>
            </thead>
            <tbody>
              {costEntries.map((entry, i) => (
                <tr key={i} className="border-b border-[#30363D]">
                  <td className="py-1 capitalize">{entry.agent?.replace(/_/g, ' ')}</td>
                  <td className="py-1 font-mono text-xs">{entry.model}</td>
                  <td className="py-1 font-mono text-xs">{entry.total_tokens?.toLocaleString()}</td>
                  <td className="py-1 font-mono text-xs">${entry.estimated_cost_usd?.toFixed(4)}</td>
                </tr>
              ))}
              {costEntries.length > 0 && (
                <tr className="font-semibold">
                  <td className="py-1">Total</td>
                  <td></td>
                  <td className="py-1 font-mono text-xs">{costEntries.reduce((s, e) => s + (e.total_tokens || 0), 0).toLocaleString()}</td>
                  <td className="py-1 font-mono text-xs">${costEntries.reduce((s, e) => s + (e.estimated_cost_usd || 0), 0).toFixed(4)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Generation Details */}
        {genMeta && (
          <div>
            <h3 className="font-bold mb-2 text-[#4ADE80]">Synthetic Generation</h3>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div><span className="opacity-50">Model:</span> {genMeta.model_used}</div>
              <div><span className="opacity-50">Time:</span> {genMeta.generation_time_ms} ms</div>
              <div><span className="opacity-50">Temperature:</span> {genMeta.temperature}</div>
              <div><span className="opacity-50">Tokens:</span> {genMeta.token_usage?.total_tokens?.toLocaleString()}</div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

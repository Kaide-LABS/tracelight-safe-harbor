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

  return (
    <div className="bg-[#0D1117] border border-[#30363D] rounded overflow-hidden text-sm">
      <div className="bg-[#161B22] p-3 border-b border-[#30363D] font-bold">
        CTO Audit Trail
      </div>
      <div className="p-4 space-y-6 max-h-[600px] overflow-y-auto">
        
        <div>
          <h3 className="font-bold mb-2 text-[#4ADE80]">Phase Timings</h3>
          <table className="w-full text-left">
            <tbody>
              {data.audit_log.filter(l => l.detail.includes("successful") || l.detail.includes("parsed")).map((log, i) => (
                <tr key={i} className="border-b border-[#30363D]">
                  <td className="py-1 opacity-70">{log.phase}</td>
                  <td className="py-1">{log.detail}</td>
                  <td className="py-1 font-mono text-xs">{new Date(log.timestamp).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

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

        <div>
          <h3 className="font-bold mb-2 text-[#4ADE80]">Generation Cost</h3>
          {data.synthetic_payload?.generation_metadata && (
            <div className="grid grid-cols-2 gap-4">
              <div>Model: {data.synthetic_payload.generation_metadata.model_used}</div>
              <div>Time: {data.synthetic_payload.generation_metadata.generation_time_ms} ms</div>
              <div>Tokens: {data.synthetic_payload.generation_metadata.token_usage.total_tokens}</div>
              <div>Est Cost: ~${((data.synthetic_payload.generation_metadata.token_usage.total_tokens / 1000) * 0.015).toFixed(3)}</div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

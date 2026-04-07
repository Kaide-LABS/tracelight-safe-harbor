import React, { useState } from 'react';

export default function DriftAlerts({ alerts }) {
  const [expanded, setExpanded] = useState(true);

  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="m-4 border border-harbor-red rounded bg-harbor-surface">
      <div 
        className="p-3 bg-harbor-red/10 cursor-pointer flex justify-between items-center"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="font-bold text-harbor-red">⚠ {alerts.length} Drift Alerts Detected</span>
        <span className="text-harbor-red">{expanded ? 'Collapse' : 'Expand'}</span>
      </div>
      
      {expanded && (
        <div className="p-4 space-y-4">
          {alerts.map((alert, idx) => (
            <div key={idx} className="border border-harbor-border p-3 rounded">
              <div className="font-bold mb-1 flex items-center">
                <span className={`mr-2 px-2 py-0.5 rounded text-xs ${alert.severity==='critical'?'bg-harbor-red text-black':'bg-harbor-amber text-black'}`}>
                  {alert.severity.toUpperCase()}
                </span>
                Q#{alert.question_id}
              </div>
              <div className="text-sm mb-1"><span className="text-harbor-blue">Policy:</span> {alert.policy_states}</div>
              <div className="text-sm mb-1"><span className="text-harbor-amber">Telemetry:</span> {alert.telemetry_shows}</div>
              <div className="text-sm text-harbor-green"><span className="font-medium">Action:</span> {alert.recommendation}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

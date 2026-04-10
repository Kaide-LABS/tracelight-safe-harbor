import React, { useState, useEffect, useRef } from 'react';
import UploadZone from './components/UploadZone';
import SchemaTerminal from './components/SchemaTerminal';
import VerdictBadge from './components/VerdictBadge';
import { useWebSocket } from './hooks/useWebSocket';
import { API_BASE } from './config';

function App() {
  const [jobId, setJobId] = useState(null);
  const [appPhase, setAppPhase] = useState('UPLOAD');
  const [auditData, setAuditData] = useState(null);

  const { events, phase: wsPhase, lastEvent } = useWebSocket(jobId);

  useEffect(() => {
    if (!jobId) return;

    if (lastEvent?.event_type === 'complete') {
      // Pipeline complete — go straight to verdict
      setAppPhase('VERDICT');
      fetch(`${API_BASE}/api/audit/${jobId}`)
        .then(res => res.json())
        .then(data => setAuditData(data))
        .catch(() => {});
    } else if (wsPhase) {
      // Any active phase — show terminal with live progress
      setAppPhase('TERMINAL');
    }
  }, [wsPhase, lastEvent, jobId]);

  const showNav = appPhase === 'UPLOAD' || appPhase === 'VERDICT';

  return (
    <div className="w-full h-full flex flex-col overflow-y-auto">
      {/* Nav bar */}
      {showNav && (
        <nav className="w-full border-b border-[#30363D] bg-[#161B22] shrink-0">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <a href="http://localhost:5173" className="flex items-center gap-2">
              <img src="/Tracelight_logo.png" alt="Tracelight" className="h-20 invert" />
            </a>
            <div className="flex items-center gap-6 text-sm">
              <span className="text-[#4ADE80] font-medium text-xs border border-[#4ADE80]/30 rounded px-2 py-0.5">Safe-Harbor</span>
              <a href={import.meta.env.VITE_LAUNCHER_URL || "http://localhost:5173"} className="text-[#E6EDF3]/40 hover:text-white transition-colors text-xs">Home</a>
            </div>
          </div>
        </nav>
      )}

      {/* Content */}
      <div className="flex-1">
        {appPhase === 'UPLOAD' && (
          <UploadZone onJobCreated={(id) => setJobId(id)} />
        )}

        {appPhase === 'TERMINAL' && (
          <SchemaTerminal events={events} />
        )}

        {appPhase === 'VERDICT' && lastEvent?.data && (
          <VerdictBadge
            jobId={jobId}
            result={lastEvent.data}
            events={events}
            onReset={() => { setJobId(null); setAppPhase('UPLOAD'); setAuditData(null); }}
            schema={auditData?.template_schema || {
              model_type: 'unknown',
              industry: 'General Corporate',
              currency: 'USD',
              total_input_cells: events.filter(e => e.event_type === 'cell_update').length
            }}
          />
        )}
      </div>
    </div>
  );
}

export default App;

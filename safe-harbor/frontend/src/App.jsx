import React, { useState, useEffect } from 'react';
import UploadZone from './components/UploadZone';
import SchemaTerminal from './components/SchemaTerminal';
import DataWaterfall from './components/DataWaterfall';
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
      setAppPhase('VERDICT');
      // Fetch full job state from audit endpoint to get real schema data
      fetch(`${API_BASE}/api/audit/${jobId}`)
        .then(res => res.json())
        .then(data => setAuditData(data))
        .catch(() => {});
    } else if (wsPhase === 'generate' || wsPhase === 'validate' || wsPhase === 'write') {
      setAppPhase('WATERFALL');
    } else if (wsPhase === 'parse' || wsPhase === 'schema_extract') {
      setAppPhase('TERMINAL');
    }
  }, [wsPhase, lastEvent, jobId]);

  return (
    <div className="w-full h-full">
      {appPhase === 'UPLOAD' && (
        <UploadZone onJobCreated={(id) => setJobId(id)} />
      )}

      {appPhase === 'TERMINAL' && (
        <SchemaTerminal events={events.filter(e => e.phase === 'parse' || e.phase === 'schema_extract')} />
      )}

      {appPhase === 'WATERFALL' && (
        <DataWaterfall events={events} />
      )}

      {appPhase === 'VERDICT' && lastEvent?.data && (
        <VerdictBadge
          jobId={jobId}
          result={lastEvent.data}
          schema={auditData?.template_schema || {
            model_type: 'unknown',
            industry: 'General Corporate',
            currency: 'USD',
            total_input_cells: events.filter(e => e.event_type === 'cell_update').length
          }}
        />
      )}
    </div>
  );
}

export default App;

import React, { useState, useEffect } from 'react';
import UploadZone from './components/UploadZone';
import SchemaTerminal from './components/SchemaTerminal';
import DataWaterfall from './components/DataWaterfall';
import VerdictBadge from './components/VerdictBadge';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const [jobId, setJobId] = useState(null);
  const [appPhase, setAppPhase] = useState('UPLOAD'); // UPLOAD, TERMINAL, WATERFALL, VERDICT
  
  const { events, phase: wsPhase, lastEvent } = useWebSocket(jobId);

  useEffect(() => {
    if (!jobId) return;

    if (lastEvent?.event_type === 'complete') {
      setAppPhase('VERDICT');
    } else if (wsPhase === 'generating' || wsPhase === 'validating' || wsPhase === 'write') {
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
          schema={events.find(e => e.phase === 'schema_extract' && e.detail.startsWith('[TYPE]')) ? 
            {
              model_type: events.find(e => e.phase === 'schema_extract' && e.detail.startsWith('[TYPE]')).detail.split(': ')[1],
              industry: "General Corporate", // Mocked for UI
              currency: "USD",
              total_input_cells: events.filter(e => e.event_type === 'cell_update').length
            } : {}
          } 
        />
      )}
    </div>
  );
}

export default App;

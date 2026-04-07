import React, { useState, useEffect } from 'react';
import QuestionnaireUpload from './components/QuestionnaireUpload';
import ProcessingTerminal from './components/ProcessingTerminal';
import AnswerGrid from './components/AnswerGrid';
import DriftAlerts from './components/DriftAlerts';
import ExportPanel from './components/ExportPanel';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const [jobId, setJobId] = useState(null);
  const [appPhase, setAppPhase] = useState('UPLOAD'); // UPLOAD, PROCESSING, COMPLETE
  const [result, setResult] = useState(null);
  const [driftAlerts, setDriftAlerts] = useState([]);
  
  const { events, lastEvent } = useWebSocket(jobId);

  useEffect(() => {
    if (!jobId) return;

    if (lastEvent?.event_type === 'complete') {
      setResult(lastEvent.data);
      setAppPhase('COMPLETE');
      
      // Fetch full result for drift alerts
      fetch(`http://localhost:8001/api/result/${jobId}`)
        .then(res => res.json())
        .then(data => {
            setDriftAlerts(data.drift_alerts);
        });
        
    } else if (events.length > 0 && appPhase === 'UPLOAD') {
      setAppPhase('PROCESSING');
    }
  }, [lastEvent, jobId, events.length]);

  return (
    <div className="w-full h-full flex flex-col bg-harbor-bg text-harbor-text">
      {appPhase === 'UPLOAD' && (
        <QuestionnaireUpload onJobCreated={(id) => setJobId(id)} />
      )}
      
      {appPhase === 'PROCESSING' && (
        <div className="flex-1 overflow-hidden">
          <ProcessingTerminal events={events} />
        </div>
      )}

      {appPhase === 'COMPLETE' && (
        <div className="flex-1 flex flex-col overflow-hidden">
          <DriftAlerts alerts={driftAlerts} />
          <AnswerGrid result={result} />
          <ExportPanel result={result} jobId={jobId} />
        </div>
      )}
    </div>
  );
}

export default App;

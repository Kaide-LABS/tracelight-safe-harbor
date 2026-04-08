import React, { useState, useEffect } from 'react';
import QuestionnaireUpload from './components/QuestionnaireUpload';
import ProcessingTerminal from './components/ProcessingTerminal';
import AnswerGrid from './components/AnswerGrid';
import DriftAlerts from './components/DriftAlerts';
import ExportPanel from './components/ExportPanel';
import { useWebSocket } from './hooks/useWebSocket';
import { API_BASE } from './config';

function App() {
  const [jobId, setJobId] = useState(null);
  const [appPhase, setAppPhase] = useState('UPLOAD');
  const [result, setResult] = useState(null);
  const [driftAlerts, setDriftAlerts] = useState([]);

  const { events, lastEvent } = useWebSocket(jobId);

  useEffect(() => {
    if (!jobId) return;

    if (lastEvent?.event_type === 'complete') {
      setResult(lastEvent.data);
      setAppPhase('COMPLETE');

      fetch(`${API_BASE}/api/result/${jobId}`)
        .then(res => res.json())
        .then(data => {
          setDriftAlerts(data.drift_alerts);
        });

    } else if (events.length > 0 && appPhase === 'UPLOAD') {
      setAppPhase('PROCESSING');
    }
  }, [lastEvent, jobId, events.length]);

  const showNav = appPhase === 'UPLOAD' || appPhase === 'COMPLETE';

  return (
    <div className="w-full h-full flex flex-col bg-[#0D1117] text-[#E6EDF3]">
      {/* Nav bar */}
      {showNav && (
        <nav className="w-full border-b border-[#30363D] bg-[#161B22] shrink-0">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
            <a href="http://localhost:5173" className="flex items-center gap-2">
              <img src="/Tracelight_logo.png" alt="Tracelight" className="h-20 invert" />
            </a>
            <div className="flex items-center gap-6 text-sm">
              <span className="text-[#58A6FF] font-medium text-xs border border-[#58A6FF]/30 rounded px-2 py-0.5">Shield-Wall</span>
              <a href="http://localhost:5173" className="text-[#E6EDF3]/40 hover:text-white transition-colors text-xs">Home</a>
            </div>
          </div>
        </nav>
      )}

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

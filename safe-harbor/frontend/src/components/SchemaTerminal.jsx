import React, { useEffect, useRef, useState } from 'react';
import SpreadsheetViewer from './SpreadsheetViewer';

export default function SchemaTerminal({ events }) {
  const terminalEndRef = useRef(null);
  const [isComplete, setIsComplete] = useState(false);
  const [jobId, setJobId] = useState(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    const completeEvent = events.find(e => e.event_type === 'complete');
    if (completeEvent) {
      setIsComplete(true);
      setJobId(completeEvent.job_id);
    }
  }, [events]);

  // Filter out internal details from terminal display
  const filteredEvents = events.filter(ev => {
    const d = (ev.detail || '').toLowerCase();
    if (d.includes('audit trail')) return false;
    return true;
  });

  return (
    <div className="h-full w-full bg-[#0D1117] text-[#4ADE80] font-mono overflow-y-auto">
      {!isComplete ? (
        <div className="p-6 max-w-4xl mx-auto">
          <div className="mb-4 text-harbor-text opacity-50"># Safe-Harbor Pipeline</div>
          {filteredEvents.map((ev, idx) => (
            <div key={idx} className="mb-1">
              {ev.detail}
            </div>
          ))}
          <div className="animate-pulse inline-block w-2 h-4 bg-[#4ADE80] ml-1 mt-1"></div>
          <div ref={terminalEndRef} />
        </div>
      ) : (
        <div className="h-full flex flex-col">
          {jobId && <SpreadsheetViewer jobId={jobId} />}
        </div>
      )}
    </div>
  );
}

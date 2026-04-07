import React, { useEffect, useRef } from 'react';

export default function SchemaTerminal({ events }) {
  const terminalEndRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="h-full w-full bg-[#0D1117] text-[#4ADE80] font-mono p-6 overflow-y-auto">
      <div className="max-w-4xl mx-auto">
        <div className="mb-4 text-harbor-text opacity-50"># Safe-Harbor Schema Extraction Agent</div>
        {events.map((ev, idx) => (
          <div key={idx} className="mb-1">
            {ev.detail}
          </div>
        ))}
        <div className="animate-pulse inline-block w-2 h-4 bg-[#4ADE80] ml-1 mt-1"></div>
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}

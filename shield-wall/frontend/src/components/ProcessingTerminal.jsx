import React, { useEffect, useRef } from 'react';

export default function ProcessingTerminal({ events }) {
  const terminalEndRef = useRef(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const getColor = (detail) => {
    if (detail.startsWith('[PARSE]')) return 'text-white';
    if (detail.startsWith('[CLASS]')) return 'text-harbor-cyan';
    if (detail.startsWith('[TELEM]')) return 'text-harbor-green';
    if (detail.startsWith('[POLICY]')) return 'text-harbor-blue';
    if (detail.startsWith('[SYNTH]')) return 'text-harbor-amber';
    if (detail.startsWith('[DRIFT]')) return 'text-harbor-red';
    return 'text-harbor-text';
  };

  return (
    <div className="h-full w-full bg-[#0D1117] font-mono p-6 overflow-y-auto">
      <div className="max-w-5xl mx-auto">
        <div className="mb-4 text-harbor-text opacity-50"># Shield-Wall Autonomous Pipeline</div>
        {events.map((ev, idx) => (
          <div key={idx} className={`mb-1 ${getColor(ev.detail)}`}>
            {ev.detail}
          </div>
        ))}
        <div className="animate-pulse inline-block w-2 h-4 bg-harbor-text ml-1 mt-1"></div>
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
}

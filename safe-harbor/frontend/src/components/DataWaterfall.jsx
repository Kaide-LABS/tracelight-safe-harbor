import React, { useState, useEffect } from 'react';

export default function DataWaterfall({ events }) {
  const [gridData, setGridData] = useState({}); // { sheet: { header: { period: value } } }
  const [activeSheet, setActiveSheet] = useState(null);
  const [messages, setMessages] = useState([]);

  useEffect(() => {
    const newGrid = { ...gridData };
    const newMsgs = [...messages];

    events.forEach(ev => {
      if (ev.event_type === 'cell_update' && ev.data) {
        const { sheet, cell_ref, value } = ev.data;
        // Simplify by just extracting header/period from detail string "Sheet.Header [Period] = value"
        const match = ev.detail.match(/(.*?)\.(.*?)\s\[(.*?)\]/);
        if (match) {
          const s = match[1];
          const h = match[2];
          const p = match[3];

          if (!newGrid[s]) newGrid[s] = {};
          if (!newGrid[s][h]) newGrid[s][h] = {};
          newGrid[s][h][p] = { value, updated: true };
          
          if (!activeSheet) setActiveSheet(s);
        }
      } else if (ev.event_type === 'validation') {
        newMsgs.push(ev.detail);
      }
    });

    setGridData(newGrid);
    setMessages(newMsgs.slice(-5)); // Keep last 5 validation msgs
  }, [events]);

  return (
    <div className="h-full flex flex-col bg-harbor-bg text-sm">
      <div className="flex border-b border-harbor-border">
        {Object.keys(gridData).map(sheet => (
          <button 
            key={sheet}
            className={`px-4 py-2 ${activeSheet === sheet ? 'border-b-2 border-harbor-green text-white' : 'text-harbor-text opacity-70'}`}
            onClick={() => setActiveSheet(sheet)}
          >
            {sheet}
          </button>
        ))}
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        {activeSheet && gridData[activeSheet] && (
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                <th className="p-2 border-b border-harbor-border w-1/4">Line Item</th>
                {/* Dynamically get periods from first row */}
                {Object.keys(Object.values(gridData[activeSheet])[0] || {}).map(p => (
                  <th key={p} className="p-2 border-b border-harbor-border text-right">{p}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(gridData[activeSheet]).map(([header, periods]) => (
                <tr key={header} className="hover:bg-harbor-surface">
                  <td className="p-2 border-b border-harbor-border font-medium">{header}</td>
                  {Object.entries(periods).map(([p, cell]) => (
                    <td key={p} className={`p-2 border-b border-harbor-border text-right font-mono ${cell.updated ? 'animate-flash-green text-harbor-green' : ''}`}>
                      {typeof cell.value === 'number' ? cell.value.toLocaleString(undefined, {maximumFractionDigits: 2}) : cell.value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="h-10 bg-harbor-surface flex items-center px-4 overflow-hidden border-t border-harbor-border">
        <div className="whitespace-nowrap font-mono text-harbor-green text-xs">
          {messages.join('   •   ')}
        </div>
      </div>
    </div>
  );
}

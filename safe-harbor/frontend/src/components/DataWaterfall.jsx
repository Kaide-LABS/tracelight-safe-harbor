import React, { useState, useEffect, useRef, useCallback } from 'react';

export default function DataWaterfall({ events, onComplete }) {
  const [gridData, setGridData] = useState({});
  const [activeSheet, setActiveSheet] = useState(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const [messages, setMessages] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null); // track last cell for highlight
  const cellEventsRef = useRef([]);
  const doneRef = useRef(false);
  const isComplete = useRef(false);

  // Track whether pipeline is done (complete event received)
  useEffect(() => {
    const hasComplete = events.some(e => e.event_type === 'complete');
    isComplete.current = hasComplete;
  }, [events]);

  // Collect cell + validation events
  useEffect(() => {
    const cells = events.filter(e => e.event_type === 'cell_update' && e.data);
    const vals = events.filter(e => e.event_type === 'validation').map(e => e.detail);
    cellEventsRef.current = cells;
    setMessages(vals.slice(-5));
  }, [events]);

  // Staggered reveal — starts slow, speeds up, slows for last few
  useEffect(() => {
    const total = cellEventsRef.current.length;
    if (visibleCount >= total) {
      // If all cells shown and pipeline complete, wait a beat then transition
      if (isComplete.current && !doneRef.current && total > 0) {
        doneRef.current = true;
        setTimeout(() => onComplete?.(), 1500);
      }
      return;
    }

    // Pacing: slow start, fast middle, slow finish
    const pct = total > 0 ? visibleCount / total : 0;
    let delay;
    if (pct < 0.05) delay = 400;       // first few cells — dramatic
    else if (pct < 0.15) delay = 200;   // warming up
    else if (pct < 0.85) delay = 50;    // bulk — fast like real generation
    else delay = 250;                    // last cells — slow for impact

    const timer = setTimeout(() => setVisibleCount(v => v + 1), delay);
    return () => clearTimeout(timer);
  }, [visibleCount, events, onComplete]);

  // Build grid from visible cells
  useEffect(() => {
    const newGrid = {};
    const visible = cellEventsRef.current.slice(0, visibleCount);
    let lastCell = null;

    visible.forEach((ev, i) => {
      const match = ev.detail.match(/(.*?)\.(.*?)\s\[(.*?)\]/);
      if (match) {
        const [, sheet, header, period] = match;
        if (!newGrid[sheet]) newGrid[sheet] = {};
        if (!newGrid[sheet][header]) newGrid[sheet][header] = {};
        newGrid[sheet][header][period] = ev.data.value;
        if (i === visible.length - 1) lastCell = { sheet, header, period };
      }
    });

    setGridData(newGrid);
    setLastUpdated(lastCell);

    // Auto-select sheet
    const sheets = Object.keys(newGrid);
    if (lastCell && sheets.includes(lastCell.sheet)) {
      setActiveSheet(lastCell.sheet);
    } else if (!activeSheet && sheets.length > 0) {
      setActiveSheet(sheets[0]);
    }
  }, [visibleCount]);

  const total = cellEventsRef.current.length;
  const pct = total > 0 ? Math.round((visibleCount / total) * 100) : 0;
  const sheets = Object.keys(gridData);

  // Get periods for active sheet
  const sheetData = gridData[activeSheet] || {};
  const allPeriods = new Set();
  Object.values(sheetData).forEach(h => Object.keys(h).forEach(p => allPeriods.add(p)));
  const periods = [...allPeriods].sort();

  const fmt = (v) => {
    if (v == null) return '';
    const n = Number(v);
    if (isNaN(n)) return String(v);
    if (Math.abs(n) >= 1e6) return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (Math.abs(n) < 1 && n !== 0) return (n * 100).toFixed(1) + '%';
    return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
  };

  return (
    <div className="h-full flex flex-col bg-harbor-bg text-sm">
      {/* Progress bar */}
      <div className="h-1.5 bg-harbor-surface relative overflow-hidden">
        <div
          className="h-full bg-harbor-green transition-all duration-200 ease-out"
          style={{ width: `${pct}%` }}
        ></div>
        {pct < 100 && (
          <div className="absolute top-0 right-0 h-full w-24 bg-gradient-to-l from-harbor-green/30 to-transparent animate-pulse"></div>
        )}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-harbor-border">
        <div className="flex items-center gap-4">
          {pct < 100 ? (
            <span className="text-harbor-green text-xs font-semibold flex items-center gap-2">
              <span className="inline-block w-2 h-2 bg-harbor-green rounded-full animate-pulse"></span>
              GENERATING SYNTHETIC DATA
            </span>
          ) : (
            <span className="text-harbor-green text-xs font-semibold">GENERATION COMPLETE</span>
          )}
          <span className="text-harbor-text/30 text-xs font-mono">{visibleCount} / {total} cells populated</span>
        </div>
        <span className="text-harbor-text/20 text-xs font-mono">{pct}%</span>
      </div>

      {/* Sheet tabs */}
      <div className="flex border-b border-harbor-border bg-harbor-surface/50">
        {sheets.map(sheet => {
          const isActive = activeSheet === sheet;
          const cellCount = Object.values(gridData[sheet] || {}).reduce((sum, h) => sum + Object.keys(h).length, 0);
          return (
            <button
              key={sheet}
              className={`px-4 py-2 text-xs transition-all ${isActive ? 'border-b-2 border-harbor-green text-white bg-harbor-bg' : 'text-harbor-text/40 hover:text-harbor-text/60'}`}
              onClick={() => setActiveSheet(sheet)}
            >
              {sheet}
              <span className="ml-1.5 text-[10px] opacity-50">({cellCount})</span>
            </button>
          );
        })}
      </div>

      {/* Spreadsheet grid */}
      <div className="flex-1 overflow-auto px-2 py-2">
        {activeSheet && Object.keys(sheetData).length > 0 && (
          <table className="w-full border-collapse">
            <thead className="sticky top-0 z-10">
              <tr>
                <th className="text-left p-2 text-[10px] font-medium uppercase tracking-wider min-w-[200px]" style={{ background: '#0D1117', color: '#6b7280', borderBottom: '2px solid #30363D' }}>
                  Line Item
                </th>
                {periods.map(p => (
                  <th key={p} className="text-right p-2 text-[10px] font-medium uppercase tracking-wider min-w-[110px]" style={{ background: '#0D1117', color: '#6b7280', borderBottom: '2px solid #30363D' }}>
                    {p}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(sheetData).map(([header, periodData]) => (
                <tr key={header} className="group hover:bg-harbor-surface/30">
                  <td className="p-2 text-xs font-medium text-harbor-text/80" style={{ borderBottom: '1px solid #1c2128' }}>
                    {header}
                  </td>
                  {periods.map(p => {
                    const val = periodData[p];
                    const isLast = lastUpdated?.sheet === activeSheet && lastUpdated?.header === header && lastUpdated?.period === p;
                    const hasVal = val != null;
                    return (
                      <td
                        key={p}
                        className="p-2 text-xs text-right font-mono transition-all duration-300"
                        style={{
                          borderBottom: '1px solid #1c2128',
                          color: hasVal ? (isLast ? '#4ADE80' : '#4ADE80cc') : '#2a2a2a',
                          background: isLast ? 'rgba(74, 222, 128, 0.12)' : 'transparent',
                          boxShadow: isLast ? 'inset 0 0 0 1px rgba(74, 222, 128, 0.3)' : 'none',
                        }}
                      >
                        {hasVal ? fmt(val) : ''}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!activeSheet && (
          <div className="flex items-center justify-center h-full text-harbor-text/20 text-sm">
            Waiting for data...
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="h-9 bg-harbor-surface flex items-center justify-between px-4 border-t border-harbor-border">
        <div className="whitespace-nowrap font-mono text-harbor-green/70 text-[10px] truncate max-w-[70%]">
          {messages.length > 0 ? messages.join('  •  ') : 'Generating...'}
        </div>
        <div className="text-[10px] text-harbor-text/30 font-mono">
          {activeSheet && `${activeSheet} • `}{periods.length} periods
        </div>
      </div>
    </div>
  );
}

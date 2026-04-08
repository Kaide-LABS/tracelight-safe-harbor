import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

const colLetter = (i) => {
  let s = '';
  while (i >= 0) {
    s = String.fromCharCode(65 + (i % 26)) + s;
    i = Math.floor(i / 26) - 1;
  }
  return s;
};

export default function TemplatePreview({ filename, templateName, onClose, onUseTemplate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSheet, setActiveSheet] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/preview/${filename}`)
      .then(r => r.json())
      .then(d => {
        setData(d);
        if (d.sheets?.length > 0) setActiveSheet(d.sheets[0].name);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [filename]);

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center">
        <div className="text-harbor-green animate-pulse">Loading template structure...</div>
      </div>
    );
  }

  if (!data) return null;

  const sheet = data.sheets?.find(s => s.name === activeSheet);
  const periods = sheet?.temporal_headers || [];
  const headers = sheet?.headers || [];
  const inputRefs = new Set((sheet?.input_cells || []).map(c => `${c.column_header}|${c.period}`));
  const formulaHeaders = new Set((sheet?.formula_cells || []).map(c => c.column_header));

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: '#1e1e1e' }}>
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 h-11 border-b" style={{ background: '#2d2d2d', borderColor: '#404040' }}>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-300 font-medium">{templateName}</span>
          <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: '#30363D', color: '#9ca3af' }}>EMPTY TEMPLATE</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onUseTemplate}
            className="px-4 py-1.5 text-xs rounded font-bold transition-colors"
            style={{ background: '#4ADE80', color: '#000' }}
          >
            Use This Template
          </button>
          <button onClick={onClose} className="px-3 py-1.5 text-xs rounded hover:bg-white/10 transition-colors" style={{ color: '#9ca3af', border: '1px solid #404040' }}>
            Close
          </button>
        </div>
      </div>

      {/* Template info bar */}
      <div className="flex items-center gap-6 px-4 h-9 border-b text-xs" style={{ background: '#252526', borderColor: '#404040', color: '#6b7280' }}>
        <span>{data.sheets?.length} sheets</span>
        <span>{data.total_input_cells} input cells</span>
        <span>{data.named_ranges?.length || 0} named ranges</span>
        <span>{data.inter_sheet_refs?.length || 0} cross-sheet links</span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 px-4 h-8 border-b text-[10px]" style={{ background: '#1e1e1e', borderColor: '#404040' }}>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm border" style={{ borderColor: '#4ADE80', background: '#4ADE8015' }}></div>
          <span style={{ color: '#6b7280' }}>Input cell (Safe-Harbor fills these)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: '#252526' }}></div>
          <span style={{ color: '#6b7280' }}>Formula cell (auto-calculated)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm" style={{ background: '#1e1e1e', border: '1px solid #2a2a2a' }}></div>
          <span style={{ color: '#6b7280' }}>Empty / header</span>
        </div>
      </div>

      {/* Spreadsheet grid */}
      <div className="flex-1 overflow-auto" style={{ background: '#1e1e1e' }}>
        <table className="border-collapse w-full" style={{ minWidth: 'max-content' }}>
          <thead className="sticky top-0 z-10">
            {/* Column letters */}
            <tr>
              <th className="sticky left-0 z-20 w-10 text-center text-[10px] font-normal" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}></th>
              <th className="text-center text-[10px] font-normal min-w-[200px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}>A</th>
              {periods.map((_, i) => (
                <th key={i} className="text-center text-[10px] font-normal min-w-[120px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}>
                  {colLetter(i + 1)}
                </th>
              ))}
            </tr>
            {/* Period headers (row 1) */}
            <tr>
              <td className="sticky left-0 z-20 text-center text-[10px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #3a3a3a' }}>1</td>
              <td className="px-3 py-1.5 text-xs font-semibold" style={{ background: '#252526', color: '#e5e7eb', borderRight: '1px solid #2a2a2a', borderBottom: '1px solid #3a3a3a' }}></td>
              {periods.map(p => (
                <td key={p} className="px-3 py-1.5 text-xs font-semibold text-center" style={{ background: '#252526', color: '#e5e7eb', borderRight: '1px solid #2a2a2a', borderBottom: '1px solid #3a3a3a' }}>{p}</td>
              ))}
            </tr>
          </thead>
          <tbody>
            {headers.map((h, rowIdx) => {
              const isFormula = formulaHeaders.has(h.header);
              return (
                <tr key={rowIdx} className="group">
                  <td className="sticky left-0 z-10 text-center text-[10px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #2a2a2a' }}>
                    {rowIdx + 2}
                  </td>
                  <td className="px-3 py-1.5 text-xs font-medium whitespace-nowrap" style={{ background: '#1e1e1e', color: '#d4d4d4', borderRight: '1px solid #2a2a2a', borderBottom: '1px solid #2a2a2a' }}>
                    {h.header}
                  </td>
                  {periods.map(p => {
                    const isInput = inputRefs.has(`${h.header}|${p}`);
                    return (
                      <td
                        key={p}
                        className="px-3 py-1.5 text-xs text-center font-mono"
                        style={{
                          background: isInput ? 'rgba(74, 222, 128, 0.08)' : isFormula ? '#252526' : '#1e1e1e',
                          color: isInput ? '#4ADE80' : isFormula ? '#6b7280' : '#3a3a3a',
                          borderRight: '1px solid #2a2a2a',
                          borderBottom: '1px solid #2a2a2a',
                          border: isInput ? '1px solid rgba(74, 222, 128, 0.25)' : undefined,
                        }}
                      >
                        {isInput ? '—' : isFormula ? 'f(x)' : ''}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Sheet tabs */}
      <div className="flex items-center h-8 border-t" style={{ background: '#252526', borderColor: '#404040' }}>
        <div className="flex items-center gap-0.5 px-2">
          {data.sheets?.map(s => (
            <button
              key={s.name}
              className="px-4 py-1 text-xs rounded-t transition-colors"
              style={{
                background: activeSheet === s.name ? '#1e1e1e' : 'transparent',
                color: activeSheet === s.name ? '#4ADE80' : '#6b7280',
                borderTop: activeSheet === s.name ? '2px solid #4ADE80' : '2px solid transparent',
              }}
              onClick={() => setActiveSheet(s.name)}
            >
              {s.name}
              <span className="ml-1 opacity-50">({s.input_cells?.length || 0})</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

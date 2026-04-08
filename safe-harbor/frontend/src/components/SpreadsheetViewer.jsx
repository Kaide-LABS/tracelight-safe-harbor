import React, { useState, useMemo } from 'react';

const colLetter = (i) => {
  let s = '';
  while (i >= 0) {
    s = String.fromCharCode(65 + (i % 26)) + s;
    i = Math.floor(i / 26) - 1;
  }
  return s;
};

const fmt = (v) => {
  if (v == null || v === '') return '';
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (Math.abs(n) >= 1e6) return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (Math.abs(n) < 1 && n !== 0) return (n * 100).toFixed(1) + '%';
  return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
};

export default function SpreadsheetViewer({ events, onClose }) {
  const gridData = useMemo(() => {
    const grid = {};
    events.forEach(ev => {
      if (ev.event_type === 'cell_update' && ev.data) {
        const match = ev.detail.match(/(.*?)\.(.*?)\s\[(.*?)\]/);
        if (match) {
          const [, sheet, header, period] = match;
          if (!grid[sheet]) grid[sheet] = {};
          if (!grid[sheet][header]) grid[sheet][header] = {};
          grid[sheet][header][period] = ev.data.value;
        }
      }
    });
    return grid;
  }, [events]);

  const sheets = Object.keys(gridData);
  const [activeSheet, setActiveSheet] = useState(sheets[0] || '');
  const [selectedCell, setSelectedCell] = useState(null);

  const { headers, periods, rows } = useMemo(() => {
    const sheetData = gridData[activeSheet] || {};
    const hdrs = Object.keys(sheetData);
    const allPeriods = new Set();
    hdrs.forEach(h => Object.keys(sheetData[h]).forEach(p => allPeriods.add(p)));
    const sortedPeriods = [...allPeriods].sort();

    const rowData = hdrs.map(h => {
      const cells = sortedPeriods.map(p => sheetData[h]?.[p] ?? '');
      return { header: h, cells };
    });

    return { headers: hdrs, periods: sortedPeriods, rows: rowData };
  }, [gridData, activeSheet]);

  const cellCount = events.filter(e => e.event_type === 'cell_update').length;

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: '#1e1e1e' }}>
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 h-10 border-b" style={{ background: '#2d2d2d', borderColor: '#404040' }}>
        <span className="text-xs text-gray-400 font-medium">safe_harbor_model.xlsx — Safe-Harbor Viewer</span>
        <div className="flex items-center gap-4">
          <span className="text-xs text-gray-500">{cellCount} cells • {sheets.length} sheets</span>
          <button onClick={onClose} className="px-3 py-1 text-xs rounded hover:bg-white/10 transition-colors" style={{ color: '#9ca3af', border: '1px solid #404040' }}>
            Minimise Spreadsheet
          </button>
        </div>
      </div>

      {/* Toolbar / Ribbon */}
      <div className="flex items-center gap-2 px-4 h-9 border-b" style={{ background: '#252526', borderColor: '#404040' }}>
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <button className="px-2 py-1 rounded hover:bg-white/10">File</button>
          <button className="px-2 py-1 rounded hover:bg-white/10">Home</button>
          <button className="px-2 py-1 rounded hover:bg-white/10">Insert</button>
          <button className="px-2 py-1 rounded hover:bg-white/10">Data</button>
          <button className="px-2 py-1 rounded hover:bg-white/10">View</button>
        </div>
        <div className="flex-1"></div>
        <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: '#4ADE80', color: '#000' }}>SYNTHETIC</span>
      </div>

      {/* Formula bar */}
      <div className="flex items-center h-8 border-b px-1" style={{ background: '#1e1e1e', borderColor: '#404040' }}>
        <div className="w-20 text-center text-xs font-mono border-r px-2 py-1" style={{ borderColor: '#404040', color: '#9ca3af' }}>
          {selectedCell || 'A1'}
        </div>
        <div className="px-2 text-xs text-gray-500 flex items-center gap-1">
          <span style={{ color: '#6b7280' }}>fx</span>
          <span className="text-gray-400 font-mono">
            {selectedCell ? (() => {
              const match = selectedCell.match(/^([A-Z]+)(\d+)$/);
              if (!match) return '';
              const colIdx = match[1].charCodeAt(0) - 65;
              const rowIdx = parseInt(match[2]) - 2;
              if (colIdx === 0) return rows[rowIdx]?.header || '';
              return rows[rowIdx]?.cells[colIdx - 1] ?? '';
            })() : ''}
          </span>
        </div>
      </div>

      {/* Spreadsheet grid */}
      <div className="flex-1 overflow-auto" style={{ background: '#1e1e1e' }}>
        <table className="border-collapse w-full" style={{ minWidth: 'max-content' }}>
          <thead className="sticky top-0 z-10">
            {/* Column letters row */}
            <tr>
              <th className="sticky left-0 z-20 w-10 text-center text-[10px] font-normal" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}></th>
              <th className="text-center text-[10px] font-normal min-w-[180px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}>
                A
              </th>
              {periods.map((_, i) => (
                <th key={i} className="text-center text-[10px] font-normal min-w-[120px]" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #404040' }}>
                  {colLetter(i + 1)}
                </th>
              ))}
            </tr>
            {/* Period headers row (row 1) */}
            <tr>
              <td className="sticky left-0 z-20 text-center text-[10px] font-normal" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #3a3a3a' }}>
                1
              </td>
              <td className="px-3 py-1.5 text-xs font-semibold" style={{ background: '#252526', color: '#e5e7eb', borderRight: '1px solid #2a2a2a', borderBottom: '1px solid #3a3a3a' }}>
              </td>
              {periods.map((p, i) => (
                <td key={p} className="px-3 py-1.5 text-xs font-semibold text-center" style={{ background: '#252526', color: '#e5e7eb', borderRight: '1px solid #2a2a2a', borderBottom: '1px solid #3a3a3a' }}>
                  {p}
                </td>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <tr key={row.header} className="group">
                {/* Row number */}
                <td className="sticky left-0 z-10 text-center text-[10px] font-normal" style={{ background: '#2d2d2d', color: '#6b7280', borderRight: '1px solid #404040', borderBottom: '1px solid #2a2a2a' }}>
                  {rowIdx + 2}
                </td>
                {/* Header cell (column A) */}
                <td
                  className="px-3 py-1.5 text-xs font-medium cursor-default whitespace-nowrap"
                  style={{
                    background: selectedCell === `A${rowIdx + 2}` ? '#264f78' : '#1e1e1e',
                    color: '#d4d4d4',
                    borderRight: '1px solid #2a2a2a',
                    borderBottom: '1px solid #2a2a2a',
                  }}
                  onClick={() => setSelectedCell(`A${rowIdx + 2}`)}
                >
                  {row.header}
                </td>
                {/* Data cells */}
                {row.cells.map((val, colIdx) => {
                  const ref = `${colLetter(colIdx + 1)}${rowIdx + 2}`;
                  const isSelected = selectedCell === ref;
                  const hasValue = val !== '' && val != null;
                  return (
                    <td
                      key={colIdx}
                      className="px-3 py-1.5 text-xs text-right font-mono cursor-default"
                      style={{
                        background: isSelected ? '#264f78' : '#1e1e1e',
                        color: hasValue ? '#4ADE80' : '#3a3a3a',
                        borderRight: '1px solid #2a2a2a',
                        borderBottom: '1px solid #2a2a2a',
                        outline: isSelected ? '2px solid #0078d4' : 'none',
                        outlineOffset: '-1px',
                      }}
                      onClick={() => setSelectedCell(ref)}
                    >
                      {hasValue ? fmt(val) : ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Sheet tabs */}
      <div className="flex items-center h-8 border-t" style={{ background: '#252526', borderColor: '#404040' }}>
        <div className="flex items-center gap-0.5 px-2">
          {sheets.map(sheet => (
            <button
              key={sheet}
              className="px-4 py-1 text-xs rounded-t transition-colors"
              style={{
                background: activeSheet === sheet ? '#1e1e1e' : 'transparent',
                color: activeSheet === sheet ? '#4ADE80' : '#6b7280',
                borderTop: activeSheet === sheet ? '2px solid #4ADE80' : '2px solid transparent',
              }}
              onClick={() => { setActiveSheet(sheet); setSelectedCell(null); }}
            >
              {sheet}
            </button>
          ))}
        </div>
        <div className="flex-1"></div>
        <div className="flex items-center gap-4 px-4 text-[10px] text-gray-500">
          <span>Ready</span>
          <span>100%</span>
        </div>
      </div>
    </div>
  );
}

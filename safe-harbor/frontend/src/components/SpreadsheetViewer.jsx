import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function SpreadsheetViewer({ jobId, onClose }) {
  const [embedUrl, setEmbedUrl] = useState(null);
  const [viewUrl, setViewUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!jobId) return;
    fetch(`${API_BASE}/api/sheets/${jobId}`, { method: 'POST' })
      .then(r => {
        if (!r.ok) throw new Error('Failed to create Google Sheet');
        return r.json();
      })
      .then(d => {
        setEmbedUrl(d.embed_url);
        setViewUrl(d.view_url);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [jobId]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col" style={{ background: '#1e1e1e' }}>
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 h-10 border-b" style={{ background: '#2d2d2d', borderColor: '#404040' }}>
        <span className="text-xs text-gray-400 font-medium">safe_harbor_model.xlsx — Safe-Harbor Viewer</span>
        <div className="flex items-center gap-3">
          {viewUrl && (
            <a
              href={viewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 text-xs rounded hover:bg-white/10 transition-colors"
              style={{ color: '#9ca3af', border: '1px solid #404040' }}
            >
              Open in Google Sheets
            </a>
          )}
          <span className="text-xs px-2 py-0.5 rounded font-medium" style={{ background: '#4ADE80', color: '#000' }}>SYNTHETIC</span>
          <button
            onClick={onClose}
            className="px-3 py-1 text-xs rounded hover:bg-white/10 transition-colors"
            style={{ color: '#9ca3af', border: '1px solid #404040' }}
          >
            Minimise Spreadsheet
          </button>
        </div>
      </div>

      {/* Content */}
      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-green-400 animate-pulse text-sm mb-2">Uploading to Google Sheets...</div>
            <div className="text-gray-500 text-xs">Formulas will be evaluated automatically</div>
          </div>
        </div>
      )}

      {error && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="text-red-400 text-sm mb-2">Failed to load spreadsheet</div>
            <div className="text-gray-500 text-xs">{error}</div>
          </div>
        </div>
      )}

      {embedUrl && !loading && (
        <iframe
          src={embedUrl}
          className="flex-1 w-full border-0"
          style={{ background: '#fff' }}
          allow="clipboard-read; clipboard-write"
        />
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { API_BASE } from '../config';

export default function TemplatePreview({ filename, templateName, onClose, onUseTemplate }) {
  const [embedUrl, setEmbedUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/sheets/template/${filename}`, { method: 'POST' })
      .then(r => {
        if (!r.ok) throw new Error('Failed to create Google Sheet');
        return r.json();
      })
      .then(d => {
        setEmbedUrl(d.embed_url);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [filename]);

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

      {/* Content */}
      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-green-400 animate-pulse text-sm">Loading template preview...</div>
        </div>
      )}

      {error && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-red-400 text-sm">{error}</div>
        </div>
      )}

      {embedUrl && !loading && (
        <iframe
          src={embedUrl}
          className="flex-1 w-full border-0"
          style={{ background: '#fff' }}
        />
      )}
    </div>
  );
}

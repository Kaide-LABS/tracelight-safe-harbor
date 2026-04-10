import React, { useState } from 'react';
import { API_BASE } from '../config';
import TemplatePreview from './TemplatePreview';

const SAMPLE_TEMPLATES = [
  { name: 'LBO Model', file: 'LBO_Model.xlsx', desc: 'Leveraged Buyout — 5 sheets, 283 input cells, debt tranches, returns analysis', enabled: true },
  { name: 'DCF Model', file: 'DCF_Model.xlsx', desc: 'Discounted Cash Flow — 6 sheets, 134 input cells, WACC, terminal value', enabled: false },
  { name: '3-Statement', file: '3_Statement_Model.xlsx', desc: 'IS + BS + CF — 3 sheets, 296 input cells, fully linked with working capital', enabled: false },
];

export default function UploadZone({ onJobCreated }) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState(null);

  const uploadFile = async (file) => {
    setError(null);
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        setError(errData.detail || "Upload failed");
        setLoading(false);
        return;
      }

      const data = await res.json();
      onJobCreated(data.job_id);
    } catch (err) {
      setError("Network error");
      setLoading(false);
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xlsm')) {
      setError("Must be an .xlsx or .xlsm file");
      return;
    }

    if (file.size > 25 * 1024 * 1024) {
      setError("File too large. Max 25MB.");
      return;
    }

    await uploadFile(file);
  };

  const handleSampleTemplate = async (filename) => {
    setError(null);
    setLoading(true);
    setPreviewTemplate(null);
    try {
      const res = await fetch(`/templates/${filename}`);
      if (!res.ok) {
        setError("Failed to load sample template");
        setLoading(false);
        return;
      }
      const blob = await res.blob();
      const file = new File([blob], filename, { type: blob.type });
      await uploadFile(file);
    } catch (err) {
      setError("Failed to load sample template");
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 overflow-y-auto">
      {/* Header */}
      <div className="w-full max-w-3xl mb-8 text-center">
        <h1 className="text-3xl font-bold mb-3">Safe-Harbor</h1>
        <p className="text-harbor-text/70 text-sm leading-relaxed max-w-xl mx-auto">
          Generate synthetic financial data for your empty Excel templates. Upload a model with headers and formulas — no real data needed. Safe-Harbor fills every input cell with financially coherent synthetic values that pass all accounting identities.
        </p>
      </div>

      {/* Upload zone */}
      <div className="border-2 border-dashed border-harbor-border rounded-lg p-10 text-center w-full max-w-3xl bg-harbor-surface relative hover:border-harbor-green transition-colors">
        <input
          type="file"
          accept=".xlsx,.xlsm"
          onChange={handleFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={loading}
        />
        <h2 className="text-xl font-bold mb-3">Drop your empty model template here</h2>
        <p className="text-harbor-border mb-4 text-sm">Upload an empty .xlsx with headers and formulas intact — no sensitive data required.</p>
        <div className="flex justify-center gap-3">
          <span className="bg-harbor-bg px-3 py-1 rounded text-xs">.xlsx</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-xs">.xlsm</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-xs">Max 25MB</span>
        </div>
      </div>

      {error && <p className="text-harbor-red mt-4 text-sm">{error}</p>}
      {loading && <p className="text-harbor-green mt-4 animate-pulse text-sm">Uploading...</p>}

      {/* How it works */}
      <div className="w-full max-w-3xl mt-6 grid grid-cols-3 gap-4 text-center text-xs text-harbor-text/50">
        <div className="bg-harbor-surface rounded p-3 border border-harbor-border">
          <div className="text-harbor-green text-lg mb-1">1</div>
          Upload empty template
        </div>
        <div className="bg-harbor-surface rounded p-3 border border-harbor-border">
          <div className="text-harbor-green text-lg mb-1">2</div>
          AI generates synthetic data
        </div>
        <div className="bg-harbor-surface rounded p-3 border border-harbor-border">
          <div className="text-harbor-green text-lg mb-1">3</div>
          Download & test in Tracelight
        </div>
      </div>

      {/* Sample templates */}
      <div className="w-full max-w-3xl mt-10">
        <p className="text-harbor-text/40 text-xs uppercase tracking-wider mb-4 text-center">Sample Templates</p>
        <div className="grid grid-cols-3 gap-4">
          {SAMPLE_TEMPLATES.map(t => (
            <div key={t.file} className={`bg-harbor-surface border border-harbor-border rounded-lg p-4 flex flex-col relative ${!t.enabled ? 'opacity-50' : ''}`}>
              {!t.enabled && (
                <span className="absolute top-2 right-2 text-[10px] font-mono text-[#58A6FF] border border-[#58A6FF]/30 bg-[#58A6FF]/10 rounded px-2 py-0.5">COMING SOON</span>
              )}
              <h3 className="font-semibold text-sm mb-1">{t.name}</h3>
              <p className="text-harbor-text/40 text-xs mb-4 flex-1">{t.desc}</p>
              {t.enabled ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => setPreviewTemplate(t)}
                    className="flex-1 px-3 py-1.5 text-xs border border-harbor-border rounded hover:border-harbor-green hover:text-harbor-green transition-colors"
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => handleSampleTemplate(t.file)}
                    disabled={loading}
                    className="flex-1 px-3 py-1.5 text-xs bg-harbor-green text-black rounded font-semibold hover:bg-harbor-green/90 transition-colors disabled:opacity-50"
                  >
                    Use
                  </button>
                </div>
              ) : (
                <div className="text-center py-1.5 text-xs text-harbor-text/30 border border-harbor-border rounded cursor-not-allowed">
                  Optimization In Progress
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Template preview modal */}
      {previewTemplate && (
        <TemplatePreview
          filename={previewTemplate.file}
          templateName={previewTemplate.name}
          onClose={() => setPreviewTemplate(null)}
          onUseTemplate={() => handleSampleTemplate(previewTemplate.file)}
        />
      )}
    </div>
  );
}

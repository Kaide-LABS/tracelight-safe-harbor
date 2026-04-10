import React, { useState } from 'react';
import { API_BASE } from '../config';
import QuestionnairePreview from './QuestionnairePreview';

const SAMPLE_TEMPLATES = [
  {
    name: 'Vendor Security Questionnaire',
    file: 'Vendor_Security_Questionnaire.xlsx',
    desc: '148 questions across 12 categories — access control, encryption, incident response, compliance, and more.',
    questions: 148,
    categories: 12,
  },
];

export default function QuestionnaireUpload({ onJobCreated }) {
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

    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.csv') && !file.name.endsWith('.pdf') && !file.name.endsWith('.docx') && !file.name.endsWith('.txt')) {
      setError("Must be an .xlsx, .csv, .pdf, .docx, or .txt file");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError("File too large. Max 50MB.");
      return;
    }

    await uploadFile(file);
  };

  const handleSampleTemplate = async (filename) => {
    setError(null);
    setLoading(true);
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
        <h1 className="text-3xl font-bold mb-3">Shield-Wall</h1>
        <p className="text-[#E6EDF3]/70 text-sm leading-relaxed max-w-xl mx-auto">
          Automate vendor security questionnaire responses. Upload a questionnaire and Shield-Wall drafts evidence-backed answers using live infrastructure telemetry and compliance policy documents.
        </p>
      </div>

      {/* Upload zone */}
      <div className="border-2 border-dashed border-[#30363D] rounded-lg p-10 text-center w-full max-w-3xl bg-[#161B22] relative hover:border-[#58A6FF] transition-colors">
        <input
          type="file"
          accept=".xlsx,.csv,.pdf,.docx,.txt"
          onChange={handleFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={loading}
        />
        <h2 className="text-xl font-bold mb-3">Drop your security questionnaire here</h2>
        <p className="text-[#30363D] mb-4 text-sm">Upload a vendor questionnaire — Shield-Wall classifies, gathers evidence, and drafts answers.</p>
        <div className="flex justify-center gap-3">
          <span className="bg-[#0D1117] px-3 py-1 rounded text-xs">.xlsx / .csv</span>
          <span className="bg-[#0D1117] px-3 py-1 rounded text-xs">.pdf / .docx</span>
          <span className="bg-[#0D1117] px-3 py-1 rounded text-xs">Max 50MB</span>
        </div>
      </div>

      {error && <p className="text-red-400 mt-4 text-sm">{error}</p>}
      {loading && <p className="text-[#58A6FF] mt-4 animate-pulse text-sm">Uploading...</p>}

      {/* How it works */}
      <div className="w-full max-w-3xl mt-6 grid grid-cols-4 gap-4 text-center text-xs text-[#E6EDF3]/50">
        <div className="bg-[#161B22] rounded p-3 border border-[#30363D]">
          <div className="text-[#58A6FF] text-lg mb-1">1</div>
          Upload questionnaire
        </div>
        <div className="bg-[#161B22] rounded p-3 border border-[#30363D]">
          <div className="text-[#58A6FF] text-lg mb-1">2</div>
          AI classifies questions
        </div>
        <div className="bg-[#161B22] rounded p-3 border border-[#30363D]">
          <div className="text-[#58A6FF] text-lg mb-1">3</div>
          Gathers telemetry & policy
        </div>
        <div className="bg-[#161B22] rounded p-3 border border-[#30363D]">
          <div className="text-[#58A6FF] text-lg mb-1">4</div>
          Drafts & exports answers
        </div>
      </div>

      {/* Sample templates */}
      <div className="w-full max-w-3xl mt-10">
        <p className="text-[#E6EDF3]/40 text-xs uppercase tracking-wider mb-4 text-center">Sample Templates</p>
        <div className="grid grid-cols-1 gap-4 max-w-md mx-auto">
          {SAMPLE_TEMPLATES.map(t => (
            <div key={t.file} className="bg-[#161B22] border border-[#30363D] rounded-lg p-5 flex flex-col">
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-semibold text-sm">{t.name}</h3>
                <span className="text-[#58A6FF] text-xs border border-[#58A6FF]/30 rounded px-2 py-0.5 shrink-0 ml-2">.xlsx</span>
              </div>
              <p className="text-[#E6EDF3]/40 text-xs mb-3 flex-1">{t.desc}</p>
              <div className="flex items-center gap-4 mb-3 text-xs text-[#E6EDF3]/50">
                <span>{t.questions} questions</span>
                <span>{t.categories} categories</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPreviewTemplate(t)}
                  className="flex-1 px-3 py-2 text-xs border border-[#30363D] rounded hover:border-[#58A6FF] hover:text-[#58A6FF] transition-colors"
                >
                  View
                </button>
                <button
                  onClick={() => handleSampleTemplate(t.file)}
                  disabled={loading}
                  className="flex-1 px-3 py-2 text-xs bg-[#58A6FF] text-black rounded font-semibold hover:bg-[#58A6FF]/90 transition-colors disabled:opacity-50"
                >
                  Use
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Preview modal */}
      {previewTemplate && (
        <QuestionnairePreview
          filename={previewTemplate.file}
          templateName={previewTemplate.name}
          onClose={() => setPreviewTemplate(null)}
          onUseTemplate={() => {
            setPreviewTemplate(null);
            handleSampleTemplate(previewTemplate.file);
          }}
        />
      )}
    </div>
  );
}

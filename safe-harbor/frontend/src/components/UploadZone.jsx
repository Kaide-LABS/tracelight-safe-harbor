import React, { useState } from 'react';

const SAMPLE_TEMPLATES = [
  { name: 'LBO Template', file: 'lbo_template.xlsx' },
  { name: 'DCF Template', file: 'dcf_template.xlsx' },
  { name: '3-Statement Template', file: 'three_statement_template.xlsx' },
];

export default function UploadZone({ onJobCreated }) {
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const uploadFile = async (file) => {
    setError(null);
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8000/api/upload', {
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
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="border-2 border-dashed border-harbor-border rounded-lg p-12 text-center w-full max-w-2xl bg-harbor-surface relative hover:border-harbor-green transition-colors">
        <input
          type="file"
          accept=".xlsx,.xlsm"
          onChange={handleFileChange}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          disabled={loading}
        />
        <h2 className="text-2xl font-bold mb-4">Drop your empty model template here</h2>
        <p className="text-harbor-border mb-6">Strip all sensitive data first. Keep headers, formulas, and structure.</p>
        <div className="flex justify-center gap-4">
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">.xlsx</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">.xlsm</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">Max 25MB</span>
        </div>
      </div>
      {error && <p className="text-harbor-red mt-4">{error}</p>}
      {loading && <p className="text-harbor-green mt-4 animate-pulse">Uploading...</p>}

      <p className="mt-10 text-harbor-border text-sm">Or choose a sample template</p>
      <div className="mt-4 flex gap-4">
        {SAMPLE_TEMPLATES.map((t) => (
          <button
            key={t.file}
            onClick={() => handleSampleTemplate(t.file)}
            disabled={loading}
            className="px-4 py-2 border border-harbor-border rounded hover:bg-harbor-surface hover:border-harbor-green transition-colors disabled:opacity-50"
          >
            {t.name}
          </button>
        ))}
      </div>
    </div>
  );
}

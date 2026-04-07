import React, { useState } from 'react';

export default function QuestionnaireUpload({ onJobCreated }) {
  const [error, setError] = useState(null);

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

    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8001/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        setError(errData.detail || "Upload failed");
        return;
      }

      const data = await res.json();
      onJobCreated(data.job_id);
    } catch (err) {
      setError("Network error");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8">
      <div className="border-2 border-dashed border-harbor-border rounded-lg p-12 text-center w-full max-w-2xl bg-harbor-surface relative hover:border-harbor-green transition-colors">
        <input 
          type="file" 
          accept=".xlsx,.csv,.pdf,.docx,.txt" 
          onChange={handleFileChange} 
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <h2 className="text-2xl font-bold mb-4">Upload a vendor security questionnaire</h2>
        <p className="text-harbor-border mb-6">We'll answer it in minutes using live telemetry and policy docs.</p>
        <div className="flex justify-center gap-4">
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">.xlsx / .csv</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">.pdf / .docx</span>
          <span className="bg-harbor-bg px-3 py-1 rounded text-sm">Max 50MB</span>
        </div>
      </div>
      {error && <p className="text-harbor-red mt-4">{error}</p>}
    </div>
  );
}

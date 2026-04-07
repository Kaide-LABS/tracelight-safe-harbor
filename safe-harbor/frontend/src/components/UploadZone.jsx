import React, { useState } from 'react';

export default function UploadZone({ onJobCreated }) {
  const [error, setError] = useState(null);

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

    setError(null);
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
          accept=".xlsx,.xlsm" 
          onChange={handleFileChange} 
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
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
      
      <div className="mt-12 flex gap-4">
        <button className="px-4 py-2 border border-harbor-border rounded hover:bg-harbor-surface">LBO Template</button>
        <button className="px-4 py-2 border border-harbor-border rounded hover:bg-harbor-surface">DCF Template</button>
        <button className="px-4 py-2 border border-harbor-border rounded hover:bg-harbor-surface">3-Statement Template</button>
      </div>
    </div>
  );
}

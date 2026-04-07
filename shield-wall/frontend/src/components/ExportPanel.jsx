import React from 'react';

export default function ExportPanel({ result, jobId }) {
  if (!result) return null;

  const handleExport = () => {
    window.location.href = `http://localhost:8001/api/export/${jobId}`;
  };

  return (
    <div className="h-16 bg-harbor-surface border-t border-harbor-border flex justify-between items-center px-6 shadow-lg z-10">
      <div className="text-sm">
        <span className="font-bold">{result.answered}</span> / {result.total_questions} answered | 
        <span className="text-harbor-green ml-2">{result.high_confidence} high conf</span> | 
        <span className="text-harbor-red ml-2">{result.drift_alerts} drift alerts</span> | 
        <span className="text-harbor-amber ml-2">{result.needs_review} need review</span>
      </div>
      <div>
        <button 
          onClick={handleExport}
          className="bg-harbor-blue text-black px-4 py-2 rounded font-bold hover:bg-harbor-blue/90"
        >
          Download Completed Questionnaire
        </button>
      </div>
    </div>
  );
}

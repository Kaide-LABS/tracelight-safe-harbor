import React, { useState } from 'react';
import AuditTrail from './AuditTrail';

export default function VerdictBadge({ jobId, result, schema }) {
  const [showAudit, setShowAudit] = useState(false);

  const handleDownload = () => {
    window.location.href = `http://localhost:8000/api/download/${jobId}`;
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 relative overflow-y-auto">
      <div className="w-full max-w-3xl bg-harbor-surface border border-harbor-green rounded-lg shadow-lg shadow-harbor-green/20 p-10 text-center relative overflow-hidden">
        
        <div className="absolute top-0 left-0 w-full h-1 bg-harbor-green"></div>
        
        <div className="w-20 h-20 bg-harbor-green/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-harbor-green" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
        </div>
        
        <h1 className="text-3xl font-bold text-harbor-text mb-8 tracking-wide">SYNTHETIC MODEL VERIFIED</h1>
        
        <div className="grid grid-cols-2 gap-8 text-left mb-10">
          <div className="space-y-3">
            <div className="flex items-center text-harbor-green"><span className="mr-3">✓</span> Balance Sheet Balanced</div>
            <div className="flex items-center text-harbor-green"><span className="mr-3">✓</span> Cash Flow Reconciled</div>
            <div className="flex items-center text-harbor-green"><span className="mr-3">✓</span> Debt Schedule Amortized</div>
            <div className="flex items-center text-harbor-green"><span className="mr-3">✓</span> Margins Within Bounds</div>
            <div className="flex items-center text-harbor-green"><span className="mr-3">✓</span> Zero Sensitive Data</div>
          </div>
          <div className="space-y-3 border-l border-harbor-border pl-8 text-sm">
            <div className="grid grid-cols-2"><span className="text-harbor-border">Model Type:</span> <span className="font-medium">{schema.model_type}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-border">Industry:</span> <span className="font-medium">{schema.industry}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-border">Currency:</span> <span className="font-medium">{schema.currency}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-border">Input Cells:</span> <span className="font-medium">{schema.total_input_cells} populated</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-border">Validation:</span> <span className="font-medium">{result.rules.filter(r=>r.passed).length}/{result.rules.length} passed</span></div>
          </div>
        </div>

        {result.status === "PASSED_WITH_PLUGS" && (
          <div className="bg-harbor-amber/10 border border-harbor-amber text-harbor-amber p-3 mb-8 rounded text-sm text-left flex items-center">
            <span className="mr-3">⚡</span>
            {result.adjustments.length} adjustment(s) made to force mathematical integrity. See audit trail.
          </div>
        )}

        <div className="flex justify-center gap-6">
          <button onClick={handleDownload} className="px-6 py-3 border border-harbor-border rounded font-medium hover:bg-harbor-bg transition-colors">
            Download .xlsx
          </button>
          <button className="px-6 py-3 bg-harbor-green text-black rounded font-bold hover:bg-harbor-green/90 transition-colors shadow-lg shadow-harbor-green/20">
            ▶ START TESTING IN TRACELIGHT
          </button>
        </div>
        
        <button onClick={() => setShowAudit(!showAudit)} className="mt-8 text-harbor-border hover:text-harbor-text text-sm underline underline-offset-4">
          {showAudit ? "Hide Audit Trail" : "View Audit Trail"}
        </button>
      </div>

      {showAudit && (
        <div className="w-full max-w-4xl mt-8">
          <AuditTrail jobId={jobId} />
        </div>
      )}
    </div>
  );
}

import React, { useState } from 'react';
import AuditTrail from './AuditTrail';
import SpreadsheetViewer from './SpreadsheetViewer';
import { API_BASE } from '../config';

const RULE_LABELS = {
  balance_sheet_identity: { label: 'Balance Sheet Identity', formula: 'Assets = Liabilities + Equity' },
  cash_flow_reconciliation: { label: 'Cash Flow Reconciliation', formula: 'Ending Cash = Beginning + Net CF' },
  net_income_linkage: { label: 'Net Income Linkage', formula: 'P&L Net Income = CF Net Income' },
  ebitda_margin_bounds: { label: 'EBITDA Margin Bounds', formula: '-50% < EBITDA/Revenue < 80%' },
  gross_margin_bounds: { label: 'Gross Margin Bounds', formula: '0% < Gross Margin < 100%' },
  net_margin_bounds: { label: 'Net Margin Bounds', formula: '-100% < Net Income/Revenue < 50%' },
  depreciation_constraint: { label: 'Depreciation Constraint', formula: 'Cum. D&A ≤ Cum. CapEx + PP&E' },
};

const fmtNum = (v) => {
  if (v == null) return '—';
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (Math.abs(n) < 1 && n !== 0) return (n * 100).toFixed(1) + '%';
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
};

export default function VerdictBadge({ jobId, result, schema, events, onReset }) {
  const [showAudit, setShowAudit] = useState(false);
  const [showViewer, setShowViewer] = useState(false);
  const [showProof, setShowProof] = useState(false);

  const handleDownload = () => {
    window.location.href = `${API_BASE}/api/download/${jobId}`;
  };

  // Group rules by rule_name for the proof section
  const ruleGroups = {};
  (result.rules || []).forEach(r => {
    const baseName = r.rule_name.replace(/^debt_schedule_.*/, 'debt_schedule');
    if (!ruleGroups[baseName]) ruleGroups[baseName] = [];
    ruleGroups[baseName].push(r);
  });

  return (
    <div className="flex flex-col items-center min-h-full p-8 relative overflow-y-auto">
      <div className="w-full flex justify-end max-w-4xl mb-4">
        <button onClick={onReset} className="px-4 py-2 text-sm border border-[#30363D] rounded hover:bg-[#161B22] transition-colors text-[#E6EDF3]/60">
          New Template
        </button>
      </div>

      <div className="w-full max-w-4xl bg-harbor-surface border border-harbor-green rounded-lg shadow-lg shadow-harbor-green/20 p-10 text-center relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1 bg-harbor-green"></div>

        <div className="w-20 h-20 bg-harbor-green/20 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-10 h-10 text-harbor-green" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
        </div>

        <h1 className="text-3xl font-bold text-harbor-text mb-2 tracking-wide">SYNTHETIC MODEL VERIFIED</h1>
        <p className="text-harbor-text/50 text-sm mb-8">All generated values pass deterministic algebraic validation — no real data used.</p>

        {/* Model info */}
        <div className="grid grid-cols-2 gap-8 text-left mb-8">
          <div className="space-y-3 border-r border-harbor-border pr-8 text-sm">
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Model Type:</span> <span className="font-medium">{schema.model_type}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Industry:</span> <span className="font-medium">{schema.industry}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Currency:</span> <span className="font-medium">{schema.currency}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Input Cells:</span> <span className="font-medium">{schema.total_input_cells} populated</span></div>
          </div>
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Validations:</span> <span className="font-medium text-harbor-green">{result.rules.filter(r=>r.passed).length}/{result.rules.length} passed</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Adjustments:</span> <span className="font-medium">{result.adjustments?.length || 0}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Status:</span> <span className={`font-medium ${result.status === 'PASSED' ? 'text-harbor-green' : 'text-harbor-amber'}`}>{result.status}</span></div>
            <div className="grid grid-cols-2"><span className="text-harbor-text/40">Sensitive Data:</span> <span className="font-medium text-harbor-green">None (100% synthetic)</span></div>
          </div>
        </div>

        {/* Validation proof summary */}
        <div className="bg-harbor-bg rounded-lg p-4 mb-8 text-left">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-harbor-text/70">Algebraic Validation Rules</h3>
            <button onClick={() => setShowProof(!showProof)} className="text-xs text-harbor-green hover:underline">
              {showProof ? 'Hide details' : 'Show proof'}
            </button>
          </div>
          <div className="space-y-2">
            {Object.entries(ruleGroups).map(([ruleName, rules]) => {
              const allPassed = rules.every(r => r.passed);
              const meta = RULE_LABELS[ruleName] || RULE_LABELS[rules[0]?.rule_name] || { label: ruleName, formula: '' };
              return (
                <div key={ruleName}>
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className={allPassed ? 'text-harbor-green' : 'text-harbor-amber'}>{allPassed ? '✓' : '⚡'}</span>
                      <span className="text-harbor-text/80 font-medium">{meta.label}</span>
                      <span className="text-harbor-text/30 font-mono">{meta.formula}</span>
                    </div>
                    <span className="text-harbor-text/40 font-mono">{rules.filter(r => r.passed).length}/{rules.length} periods</span>
                  </div>

                  {/* Expanded proof rows */}
                  {showProof && (
                    <div className="ml-6 mt-1 mb-2 space-y-0.5">
                      {rules.map((r, i) => (
                        <div key={i} className="flex items-center gap-4 text-[11px] font-mono text-harbor-text/50">
                          <span className="w-16">{r.period}</span>
                          <span>expected: <span className="text-harbor-text/70">{fmtNum(r.expected)}</span></span>
                          <span>actual: <span className={r.passed ? 'text-harbor-green' : 'text-harbor-amber'}>{fmtNum(r.actual)}</span></span>
                          <span>delta: <span className={Math.abs(r.delta || 0) < 0.01 ? 'text-harbor-green' : 'text-harbor-amber'}>{fmtNum(r.delta)}</span></span>
                          {r.adjustment_applied && <span className="text-harbor-amber">plugged</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {result.status === "PASSED_WITH_PLUGS" && (
          <div className="bg-harbor-amber/10 border border-harbor-amber text-harbor-amber p-3 mb-8 rounded text-sm text-left flex items-center">
            <span className="mr-3">⚡</span>
            {result.adjustments.length} adjustment(s) applied to force mathematical integrity. Values were deterministically corrected — no manual intervention.
          </div>
        )}

        <div className="flex justify-center gap-4">
          <button onClick={handleDownload} className="px-6 py-3 border border-harbor-border rounded font-medium hover:bg-harbor-bg transition-colors">
            Download .xlsx
          </button>
          <button onClick={() => setShowViewer(true)} className="px-6 py-3 border border-harbor-green text-harbor-green rounded font-bold hover:bg-harbor-green/10 transition-colors">
            View Data
          </button>
          <button onClick={() => window.open('https://tracelight.ai', '_blank')} className="px-6 py-3 bg-harbor-green text-black rounded font-bold hover:bg-harbor-green/90 transition-colors shadow-lg shadow-harbor-green/20">
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

      {showViewer && (
        <SpreadsheetViewer jobId={jobId} onClose={() => setShowViewer(false)} />
      )}
    </div>
  );
}

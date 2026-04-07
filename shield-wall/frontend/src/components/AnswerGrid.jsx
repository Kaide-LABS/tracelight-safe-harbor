import React, { useState } from 'react';

export default function AnswerGrid({ result }) {
  const [filter, setFilter] = useState('ALL');
  const [expanded, setExpanded] = useState(null);

  if (!result || !result.answers) return null;

  const filteredAnswers = result.answers.filter(ans => {
    if (filter === 'REVIEW') return ans.needs_human_review;
    if (filter === 'DRIFT') return ans.drift_detected;
    if (filter === 'HIGH') return ans.confidence === 'high';
    return true;
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 border-b border-harbor-border flex gap-4 bg-harbor-surface">
        <button onClick={() => setFilter('ALL')} className={`px-3 py-1 rounded ${filter==='ALL'?'bg-harbor-blue text-black':'text-harbor-text'}`}>All</button>
        <button onClick={() => setFilter('REVIEW')} className={`px-3 py-1 rounded ${filter==='REVIEW'?'bg-harbor-red text-black':'text-harbor-text'}`}>Needs Review</button>
        <button onClick={() => setFilter('DRIFT')} className={`px-3 py-1 rounded ${filter==='DRIFT'?'bg-harbor-amber text-black':'text-harbor-text'}`}>Drift</button>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-harbor-surface border-b border-harbor-border">
              <th className="p-2">#</th>
              <th className="p-2">Answer</th>
              <th className="p-2">Confidence</th>
              <th className="p-2">Review</th>
            </tr>
          </thead>
          <tbody>
            {filteredAnswers.map((ans) => {
              const isExp = expanded === ans.question_id;
              return (
                <React.Fragment key={ans.question_id}>
                  <tr 
                    className="border-b border-harbor-border hover:bg-harbor-surface cursor-pointer"
                    onClick={() => setExpanded(isExp ? null : ans.question_id)}
                  >
                    <td className="p-2 align-top">{ans.question_id}</td>
                    <td className="p-2">
                      <div className="truncate max-w-xl font-medium">{ans.answer_text}</div>
                    </td>
                    <td className="p-2">
                      <span className={`px-2 py-1 rounded text-xs ${ans.confidence==='high'?'bg-harbor-green text-black':ans.confidence==='medium'?'bg-harbor-amber text-black':'bg-harbor-red text-black'}`}>
                        {ans.confidence.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-2">
                      <input type="checkbox" checked={ans.needs_human_review} readOnly />
                    </td>
                  </tr>
                  {isExp && (
                    <tr className="bg-[#0D1117] border-b border-harbor-border">
                      <td colSpan="4" className="p-4">
                        <div className="mb-2"><strong>Answer:</strong> {ans.answer_text}</div>
                        {ans.drift_detected && (
                          <div className="text-harbor-red mb-2"><strong>Drift:</strong> {ans.drift_detail}</div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

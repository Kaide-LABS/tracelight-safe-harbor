import React from 'react';
import { SAFE_HARBOR_URL, SHIELD_WALL_URL } from './config';

function App() {
  return (
    <div className="min-h-screen bg-[#0D1117] text-[#E6EDF3] flex flex-col">

      {/* Nav bar */}
      <nav className="w-full border-b border-[#30363D] bg-[#161B22]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <a href="http://localhost:5173" className="flex items-center gap-2">
            <img src="/Tracelight_logo.png" alt="Tracelight" className="h-20 invert" />
          </a>
          <div className="flex items-center gap-6 text-sm text-[#E6EDF3]/50">
            <a href={SAFE_HARBOR_URL} className="hover:text-[#4ADE80] transition-colors">Safe-Harbor</a>
            <a href={SHIELD_WALL_URL} className="hover:text-[#4ADE80] transition-colors">Shield-Wall</a>
            <a href="https://tracelight.ai" target="_blank" className="hover:text-white transition-colors">tracelight.ai</a>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">

        <div className="mb-16 text-center">
          <p className="text-sm text-[#4ADE80] font-mono tracking-widest mb-4">AI SIDECARS</p>
          <h1 className="text-5xl font-bold tracking-tight text-white mb-4">Internal Tools Suite</h1>
          <p className="text-lg text-[#E6EDF3]/40 max-w-xl mx-auto">
            Two AI-powered sidecars that operate at the boundaries of Tracelight's core DAG engine — never touching it.
          </p>
        </div>

        <div className="flex gap-8 max-w-5xl w-full">

          {/* Safe-Harbor Card */}
          <div className="flex-1 bg-[#161B22] border border-[#30363D] rounded-xl p-8 hover:border-[#4ADE80] transition-all group flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div className="w-12 h-12 bg-[#4ADE80]/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-[#4ADE80]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
              </div>
              <span className="text-[10px] font-mono text-[#E6EDF3]/30 border border-[#30363D] rounded px-2 py-0.5">PRE-CORE</span>
            </div>
            <h2 className="text-2xl font-bold mb-1">Safe-Harbor</h2>
            <p className="text-[#4ADE80] font-mono text-xs mb-4">Synthetic Financial Data Generator</p>
            <p className="text-[#E6EDF3]/40 text-sm mb-8 flex-1 leading-relaxed">
              Upload empty Excel templates and generate financially coherent synthetic data. Balance sheets balance, cash flows reconcile, margins stay realistic. Zero sensitive data exposure.
            </p>
            <div className="flex items-center gap-3 text-xs text-[#E6EDF3]/20 mb-6">
              <span className="bg-[#0D1117] px-2 py-1 rounded">Gemini 3 Flash</span>
              <span className="bg-[#0D1117] px-2 py-1 rounded">GPT-4o</span>
              <span className="bg-[#0D1117] px-2 py-1 rounded">6 Validation Rules</span>
            </div>
            <a href={SAFE_HARBOR_URL} className="block w-full py-3 text-center bg-[#0D1117] border border-[#30363D] hover:bg-[#4ADE80] hover:text-black hover:border-[#4ADE80] rounded-lg font-semibold transition-all text-sm">
              Launch Safe-Harbor
            </a>
          </div>

          {/* Shield-Wall Card */}
          <div className="flex-1 bg-[#161B22] border border-[#30363D] rounded-xl p-8 hover:border-[#58A6FF] transition-all group flex flex-col">
            <div className="flex items-center justify-between mb-6">
              <div className="w-12 h-12 bg-[#58A6FF]/10 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-[#58A6FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
              </div>
              <span className="text-[10px] font-mono text-[#E6EDF3]/30 border border-[#30363D] rounded px-2 py-0.5">PARALLEL</span>
            </div>
            <h2 className="text-2xl font-bold mb-1">Shield-Wall</h2>
            <p className="text-[#58A6FF] font-mono text-xs mb-4">Autonomous InfoSec Responder</p>
            <p className="text-[#E6EDF3]/40 text-sm mb-8 flex-1 leading-relaxed">
              Upload vendor security questionnaires and get AI-generated answers backed by live infrastructure telemetry and policy documents. Drift detection flags real compliance gaps.
            </p>
            <div className="flex items-center gap-3 text-xs text-[#E6EDF3]/20 mb-6">
              <span className="bg-[#0D1117] px-2 py-1 rounded">Gemini + GPT-4o</span>
              <span className="bg-[#0D1117] px-2 py-1 rounded">ChromaDB RAG</span>
              <span className="bg-[#0D1117] px-2 py-1 rounded">5 Drift Checks</span>
            </div>
            <a href={SHIELD_WALL_URL} className="block w-full py-3 text-center bg-[#0D1117] border border-[#30363D] hover:bg-[#58A6FF] hover:text-black hover:border-[#58A6FF] rounded-lg font-semibold transition-all text-sm">
              Launch Shield-Wall
            </a>
          </div>

        </div>

        <div className="mt-16 text-[#E6EDF3]/20 text-xs font-mono text-center">
          Anti-Replication Compliant — Does not touch the core DAG engine
        </div>

      </div>
    </div>
  );
}

export default App;

import React from 'react';

function App() {
  return (
    <div className="min-h-screen bg-harbor-bg text-harbor-text flex flex-col items-center justify-center p-8">
      
      <div className="mb-16 text-center">
        <h1 className="text-4xl font-bold tracking-widest text-white mb-2">TRACELIGHT</h1>
        <div className="h-1 w-24 bg-harbor-green mx-auto mb-4"></div>
        <p className="text-xl text-harbor-border font-mono tracking-widest">AI SIDECARS</p>
      </div>

      <div className="flex gap-8 max-w-6xl w-full">
        
        {/* Safe-Harbor Card */}
        <div className="flex-1 bg-harbor-surface border border-harbor-border rounded-xl p-8 hover:border-harbor-green transition-all relative overflow-hidden flex flex-col shadow-xl">
          <div className="absolute top-0 right-0 bg-harbor-bg px-3 py-1 text-xs text-harbor-border border-b border-l border-harbor-border rounded-bl">PRE-CORE — For Prospects</div>
          <div className="w-16 h-16 bg-harbor-green/10 rounded-xl flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-harbor-green" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
          </div>
          <h2 className="text-2xl font-bold mb-2">Safe-Harbor</h2>
          <h3 className="text-harbor-green font-mono text-sm mb-4">Synthetic Financial Data Fabric</h3>
          <p className="text-harbor-border mb-8 flex-1">
            Generate mathematically verified synthetic data for empty Excel templates. Zero sensitive data. Instant testing.
          </p>
          <a href="http://localhost:5174" className="block w-full py-3 text-center bg-harbor-bg border border-harbor-border hover:bg-harbor-green hover:text-black hover:border-harbor-green rounded font-bold transition-colors">
            Launch Safe-Harbor
          </a>
        </div>

        {/* Shield-Wall Card */}
        <div className="flex-1 bg-harbor-surface border border-harbor-border rounded-xl p-8 hover:border-harbor-blue transition-all relative overflow-hidden flex flex-col shadow-xl">
          <div className="absolute top-0 right-0 bg-harbor-bg px-3 py-1 text-xs text-harbor-border border-b border-l border-harbor-border rounded-bl">PARALLEL — Internal Ops</div>
          <div className="w-16 h-16 bg-harbor-blue/10 rounded-xl flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-harbor-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
          </div>
          <h2 className="text-2xl font-bold mb-2">Shield-Wall</h2>
          <h3 className="text-harbor-blue font-mono text-sm mb-4">Autonomous InfoSec Responder</h3>
          <p className="text-harbor-border mb-8 flex-1">
            Answer vendor security questionnaires in minutes. AI-powered with live infrastructure evidence.
          </p>
          <a href="http://localhost:5175" className="block w-full py-3 text-center bg-harbor-bg border border-harbor-border hover:bg-harbor-blue hover:text-black hover:border-harbor-blue rounded font-bold transition-colors">
            Launch Shield-Wall
          </a>
        </div>

      </div>

      <div className="mt-16 text-harbor-border/50 text-xs font-mono uppercase tracking-widest text-center">
        Anti-Replication Compliant<br/>Does not touch the core DAG engine
      </div>

    </div>
  );
}

export default App;

import React from 'react';

export default function ErrorBanner({ message, onReset }) {
  if (!message) return null;
  return (
    <div className="bg-harbor-red text-black p-4 flex justify-between items-center z-50 shadow-lg">
      <div>
        <strong>Error: </strong> {message}
      </div>
      <button 
        onClick={onReset}
        className="px-4 py-1 bg-black text-harbor-red rounded hover:bg-black/80 font-bold"
      >
        Try Again
      </button>
    </div>
  );
}

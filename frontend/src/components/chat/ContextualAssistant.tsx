import React, { useState } from 'react';

interface ContextualAssistantProps {
  incidentId?: string;
}

export const ContextualAssistant: React.FC<ContextualAssistantProps> = ({ incidentId = 'inc-seed-01' }) => {
  const [messages, setMessages] = useState([
    { sender: 'assistant', text: `Contextual Reliability Assistant initialized for Incident ${incidentId}. Ask me to summarize evidence, explain RCA hypotheses, or check historical baselines.` }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = { sender: 'user', text: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: `Analyzing incident ${incidentId} context: The battery discharge rate drift was verified against historical 14-day MAD baselines.`
        }
      ]);
    }, 600);
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 flex flex-col h-[500px] shadow-xl">
      <div className="pb-3 border-b border-slate-800 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <span>💬</span> Contextual Assistant
        </h4>
        <span className="text-[10px] font-mono bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
          {incidentId}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto py-3 space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-3 rounded-lg text-xs leading-relaxed ${m.sender === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-950 text-slate-300 border border-slate-800'}`}>
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <div className="pt-2 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask contextual assistant..."
          className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={handleSend}
          className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg transition"
        >
          Send
        </button>
      </div>
    </div>
  );
};

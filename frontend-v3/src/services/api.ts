const API_BASE = '/api/v1';

export async function sendChatMessage(message: string, sessionId: string = 'default') {
  const res = await fetch(`${API_BASE}/chat/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchChatHistory(sessionId: string = 'default') {
  const res = await fetch(`${API_BASE}/chat/history?session_id=${sessionId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

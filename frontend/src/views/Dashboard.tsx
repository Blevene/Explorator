import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createSession, listSessions } from '../services/api';
import { useSessionStore } from '../stores/sessionStore';

export default function Dashboard() {
  const { sessions, setSessions } = useSessionStore();
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    listSessions().then((data) => setSessions(data.items)).catch(console.error);
  }, [setSessions]);

  const handleCreate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    try {
      const session = await createSession(prompt);
      navigate(`/session/${session.session_id}`);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-2">MusicExplorator</h1>
      <p className="text-gray-400 mb-8">Genre-aware musical exploration engine</p>

      <div className="mb-8 p-6 bg-gray-900 rounded-lg border border-gray-800">
        <h2 className="text-lg font-semibold mb-3">New Exploration</h2>
        <div className="flex gap-3">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            placeholder="Dream pop in A major, wistful and haunted, 8 bars..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-md px-4 py-2 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
          <button
            onClick={handleCreate}
            disabled={loading || !prompt.trim()}
            className="px-6 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded-md font-medium transition-colors"
          >
            {loading ? 'Creating...' : 'Explore'}
          </button>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Sessions</h2>
      {sessions.length === 0 ? (
        <p className="text-gray-500">No sessions yet. Start a new exploration above.</p>
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              onClick={() => navigate(`/session/${s.session_id}`)}
              className="p-4 bg-gray-900 rounded-lg border border-gray-800 hover:border-gray-600 cursor-pointer transition-colors"
            >
              <div className="flex justify-between items-center">
                <span className="text-gray-200">{s.prompt || 'Untitled session'}</span>
                <span className="text-xs text-gray-500">{s.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

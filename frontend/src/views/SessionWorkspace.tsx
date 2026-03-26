import { useParams, Link } from 'react-router-dom';

export default function SessionWorkspace() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="max-w-6xl mx-auto p-8">
      <Link to="/" className="text-purple-400 hover:text-purple-300 text-sm mb-4 inline-block">
        &larr; Back to Dashboard
      </Link>
      <h1 className="text-2xl font-bold mb-4">Session: {id}</h1>
      <div className="p-6 bg-gray-900 rounded-lg border border-gray-800">
        <p className="text-gray-400">
          Workspace will be implemented in M1. This session is ready for exploration rounds.
        </p>
      </div>
    </div>
  );
}

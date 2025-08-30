import { useEffect, useState } from 'react';

interface RAGConfig {
  retrieval_top_k: number;
  min_chunks: number;
  confidence_threshold: number;
  relevance_threshold: number;
  max_context_length: number;
  temperature: number;
  enable_fallback: boolean;
}

export default function Config() {
  const [config, setConfig] = useState<RAGConfig | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('http://localhost:8000/config')
      .then(res => res.json())
      .then(data => setConfig(data));
  }, []);

  const updateConfig = () => {
    if (!config) return;
    fetch('http://localhost:8000/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }).then(res => {
      if (res.ok) {
        setMessage('Configuration updated successfully');
      } else {
        setMessage('Error updating configuration');
      }
    });
  };

  if (!config) return <div>Loading...</div>;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">RAG Configuration</h1>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label>Retrieval Top K</label>
          <input
            type="number"
            value={config.retrieval_top_k}
            onChange={e => setConfig({ ...config, retrieval_top_k: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Min Chunks</label>
          <input
            type="number"
            value={config.min_chunks}
            onChange={e => setConfig({ ...config, min_chunks: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Confidence Threshold</label>
          <input
            type="number"
            step="0.1"
            value={config.confidence_threshold}
            onChange={e => setConfig({ ...config, confidence_threshold: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Relevance Threshold</label>
          <input
            type="number"
            step="0.1"
            value={config.relevance_threshold}
            onChange={e => setConfig({ ...config, relevance_threshold: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Max Context Length</label>
          <input
            type="number"
            value={config.max_context_length}
            onChange={e => setConfig({ ...config, max_context_length: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Temperature</label>
          <input
            type="number"
            step="0.1"
            value={config.temperature}
            onChange={e => setConfig({ ...config, temperature: +e.target.value })}
            className="border p-2 w-full"
          />
        </div>
        <div>
          <label>Enable Fallback</label>
          <input
            type="checkbox"
            checked={config.enable_fallback}
            onChange={e => setConfig({ ...config, enable_fallback: e.target.checked })}
            className="border p-2"
          />
        </div>
      </div>
      <button onClick={updateConfig} className="bg-green-500 text-white px-4 py-2 rounded mt-4">Update Config</button>
      {message && <p className="mt-4">{message}</p>}
      <div className="mt-8">
        <a href="/" className="bg-gray-500 text-white px-4 py-2 rounded">Back to Dashboard</a>
      </div>
    </div>
  );
}
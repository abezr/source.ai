import { useEffect, useState } from 'react';

export default function Dashboard() {
  const [stats, setStats] = useState({ total_books_indexed: 0, jobs_in_queue: 0 });

  useEffect(() => {
    fetch('http://localhost:8000/stats')
      .then(res => res.json())
      .then(data => setStats(data));
  }, []);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-blue-100 p-4 rounded">
          <h2 className="text-lg font-semibold">Total Books Indexed</h2>
          <p className="text-3xl">{stats.total_books_indexed}</p>
        </div>
        <div className="bg-green-100 p-4 rounded">
          <h2 className="text-lg font-semibold">Jobs in Queue</h2>
          <p className="text-3xl">{stats.jobs_in_queue}</p>
        </div>
      </div>
      <div className="mt-8">
        <a href="/books" className="bg-blue-500 text-white px-4 py-2 rounded mr-4">Manage Books</a>
        <a href="/config" className="bg-green-500 text-white px-4 py-2 rounded">Configure RAG</a>
      </div>
    </div>
  );
}

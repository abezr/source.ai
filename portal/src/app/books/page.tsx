import { useEffect, useState } from 'react';

interface Book {
  id: number;
  title: string;
  author: string;
  source_path: string | null;
}

export default function Books() {
  const [books, setBooks] = useState<Book[]>([]);
  const [newBook, setNewBook] = useState({ title: '', author: '' });

  useEffect(() => {
    fetchBooks();
  }, []);

  const fetchBooks = () => {
    fetch('http://localhost:8000/books/')
      .then(res => res.json())
      .then(data => setBooks(data));
  };

  const createBook = () => {
    fetch('http://localhost:8000/books/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newBook),
    }).then(() => {
      fetchBooks();
      setNewBook({ title: '', author: '' });
    });
  };

  const uploadFile = (bookId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    fetch(`http://localhost:8000/books/${bookId}/upload`, {
      method: 'POST',
      body: formData,
    }).then(() => fetchBooks());
  };

  const getStatus = (book: Book) => {
    if (!book.source_path) return 'Not Uploaded';
    return 'Uploaded';
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Book Management</h1>
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-2">Create New Book</h2>
        <input
          type="text"
          placeholder="Title"
          value={newBook.title}
          onChange={e => setNewBook({ ...newBook, title: e.target.value })}
          className="border p-2 mr-2"
        />
        <input
          type="text"
          placeholder="Author"
          value={newBook.author}
          onChange={e => setNewBook({ ...newBook, author: e.target.value })}
          className="border p-2 mr-2"
        />
        <button onClick={createBook} className="bg-blue-500 text-white px-4 py-2 rounded">Create</button>
      </div>
      <table className="w-full border">
        <thead>
          <tr>
            <th className="border p-2">ID</th>
            <th className="border p-2">Title</th>
            <th className="border p-2">Author</th>
            <th className="border p-2">Status</th>
            <th className="border p-2">Upload</th>
          </tr>
        </thead>
        <tbody>
          {books.map(book => (
            <tr key={book.id}>
              <td className="border p-2">{book.id}</td>
              <td className="border p-2">{book.title}</td>
              <td className="border p-2">{book.author}</td>
              <td className="border p-2">{getStatus(book)}</td>
              <td className="border p-2">
                <input
                  type="file"
                  accept=".pdf,.djvu"
                  onChange={e => e.target.files && uploadFile(book.id, e.target.files[0])}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-8">
        <a href="/" className="bg-gray-500 text-white px-4 py-2 rounded">Back to Dashboard</a>
      </div>
    </div>
  );
}
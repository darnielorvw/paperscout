import { useEffect, useState } from 'react';

function App() {
  // Hier werden die Paper gespeichert, die wir von der FastAPI holen
  const [papers, setPapers] = useState([]);

  // Sobald die Seite lädt, holen wir die Daten vom Python-Backend
  useEffect(() => {
    // Ersetze die URL später mit deiner echten FastAPI-URL (z.B. http://127.0.0.1:8000/papers)
    // Für den Start simulieren wir hier Beispieldaten
    const mockData = [
      { id: 1, title: "AI in Higher Education", journal: "Harvard Business Review", ai_score: "95%", reason: "Passt perfekt zu Ihrer Vorlesung 'Digitale Transformation' im Master." },
      { id: 2, title: "Automated Literature Reviews", journal: "Nature", ai_score: "88%", reason: "Relevant für die Methodik-Vorlesung von Prof. Winnen." }
    ];
    setPapers(mockData);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      {/* Header */}
      <header className="mb-8 border-b pb-4">
        <h1 className="text-3xl font-bold text-gray-900">PaperScout 🚀</h1>
        <p className="text-gray-600">Monatliche Literaturrecherche für Lehrstühle</p>
      </header>

      {/* Main Content */}
      <main>
        <h2 className="text-xl font-semibold mb-4 text-gray-800">Neue Vorschläge für diesen Monat</h2>
        
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-100">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Titel / Journal</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">KI-Relevanz</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">KI-Begründung</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Aktion</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {papers.map((paper) => (
                <tr key={paper.id}>
                  <td className="px-6 py-4">
                    <div className="font-semibold text-gray-900">{paper.title}</div>
                    <div className="text-sm text-gray-500">{paper.journal}</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="bg-green-100 text-green-800 text-xs font-semibold px-2.5 py-0.5 rounded">
                      {paper.ai_score} Match
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 max-w-md">
                    {paper.reason}
                  </td>
                  <td className="px-6 py-4 text-sm font-medium space-x-2">
                    <button className="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">Merken</button>
                    <button className="text-gray-500 hover:text-red-500 px-3 py-1">Verwerfen</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

export default App;
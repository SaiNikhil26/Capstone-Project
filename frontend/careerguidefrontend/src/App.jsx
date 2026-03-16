import { useState } from 'react';
import SearchBar from './components/SearchBar';
import AdvisorCard from './components/AdvisorCard';
import CareerCard from './components/CareerCard';
import CourseList from './components/CourseList';
import './App.css';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleSearch = async (query) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8080/recommend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to fetch recommendations');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="hero-section">
        <div className="hero-content">
          <h1 className="title text-gradient">CourseAI</h1>
          <p className="subtitle">Discover your perfect learning path, perfectly tailored to your goals and current skill level.</p>
        </div>
        <SearchBar onSearch={handleSearch} isLoading={isLoading} />
      </header>

      <main className="content-container">
        {error && (
          <div className="error-message glass-panel">
            ⚠️ {error}
          </div>
        )}

        {result && (
          <div className="results-animate-in">
            <div className="results-header">
              <h2>Your Custom Learning Pathway</h2>
              <div className="intent-tags">
                <span className="tag">Topic: {result.intent.topic}</span>
                <span className="tag">Level: {result.intent.level}</span>
              </div>
            </div>

            <CareerCard alignment={result.career_alignment} />
            <AdvisorCard recommendation={result.recommendation} skillGap={result.skill_gap} />
            <CourseList stages={result.learning_path} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

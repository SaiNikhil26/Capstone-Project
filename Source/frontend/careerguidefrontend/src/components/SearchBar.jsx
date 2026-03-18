import { useState } from 'react';
import { Search, Loader2, Filter } from 'lucide-react';
import './SearchBar.css';

export default function SearchBar({ onSearch, isLoading }) {
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [minRating, setMinRating] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      const filters = {};
      if (difficulty) filters.difficulty = difficulty;
      if (minRating) filters.min_rating = parseFloat(minRating);
      onSearch(query, Object.keys(filters).length > 0 ? filters : null);
    }
  };

  return (
    <div className="search-bar-wrapper">
      <form className="search-bar-container" onSubmit={handleSubmit}>
        <div className="search-input-wrapper">
          <Search className="search-icon" size={20} />
          <input
            type="text"
            className="search-input"
            placeholder="What do you want to learn? (e.g. 'I want to learn AI as a beginner')"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
          />
          <button 
            type="button" 
            className={`filter-btn ${showFilters ? 'active' : ''}`}
            onClick={() => setShowFilters(!showFilters)}
            title="Toggle Filters"
          >
            <Filter size={18} />
          </button>
          <button 
            type="submit" 
            className="search-btn"
            disabled={!query.trim() || isLoading}
          >
            {isLoading ? <Loader2 className="spinner" size={18} /> : 'Discover'}
          </button>
        </div>
      </form>

      {showFilters && (
        <div className="filters-container glass-panel">
          <div className="filter-group">
            <label>Difficulty</label>
            <select 
              value={difficulty} 
              onChange={(e) => setDifficulty(e.target.value)}
              className="filter-select"
            >
              <option value="">Any Difficulty</option>
              <option value="Beginner">Beginner</option>
              <option value="Intermediate">Intermediate</option>
              <option value="Advanced">Advanced</option>
            </select>
          </div>
          <div className="filter-group">
            <label>Min Rating</label>
            <input 
              type="number" 
              min="0" max="5" step="0.1"
              value={minRating} 
              onChange={(e) => setMinRating(e.target.value)}
              className="filter-input"
              placeholder="e.g. 4.5"
            />
          </div>
        </div>
      )}
    </div>
  );
}

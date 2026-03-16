import { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import './SearchBar.css';

export default function SearchBar({ onSearch, isLoading }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSearch(query);
    }
  };

  return (
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
          type="submit" 
          className="search-btn"
          disabled={!query.trim() || isLoading}
        >
          {isLoading ? <Loader2 className="spinner" size={18} /> : 'Discover'}
        </button>
      </div>
    </form>
  );
}

/**
 * 手動検索コンポーネント
 */
import React, { useState } from 'react';
import { searchAPI, SearchResult } from '../services/api';
import SearchResults from './SearchResults';

const ManualSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);

  const handleSearch = async () => {
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    try {
      const results = await searchAPI.search({ query, limit: 20 });
      setSearchResults(results);
    } catch (error) {
      console.error('検索エラー:', error);
      alert('検索中にエラーが発生しました');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.searchSection}>
        <h2 style={styles.title}>ナレッジグラフ検索</h2>

        <div style={styles.searchBox}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="検索キーワードを入力..."
            style={styles.input}
            disabled={isLoading}
          />
          <button
            onClick={handleSearch}
            disabled={!query.trim() || isLoading}
            style={{
              ...styles.searchButton,
              ...((!query.trim() || isLoading) && styles.searchButtonDisabled),
            }}
          >
            {isLoading ? '検索中...' : '🔍 検索'}
          </button>
        </div>

        <div style={styles.hint}>
          💡 人名、プロジェクト名、技術用語などで検索できます
        </div>
      </div>

      {searchResults && (
        <div style={styles.resultsSection}>
          <SearchResults results={searchResults} />
        </div>
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '20px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  searchSection: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
  },
  title: {
    margin: '0 0 20px 0',
    fontSize: '24px',
    fontWeight: 'bold',
  },
  searchBox: {
    display: 'flex',
    gap: '10px',
    marginBottom: '12px',
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '16px',
  },
  searchButton: {
    padding: '12px 24px',
    backgroundColor: '#1976d2',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  searchButtonDisabled: {
    backgroundColor: '#ccc',
    cursor: 'not-allowed',
  },
  hint: {
    fontSize: '13px',
    color: '#666',
    fontStyle: 'italic',
  },
  resultsSection: {
    flex: 1,
    overflow: 'hidden',
  },
};

export default ManualSearch;

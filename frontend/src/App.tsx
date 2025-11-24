/**
 * メインアプリケーション
 */
import React, { useState } from 'react';
import ChatInterface from './components/ChatInterface';
import ManualSearch from './components/ManualSearch';

type Tab = 'chat' | 'search';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('chat');

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <h1 style={styles.headerTitle}>Graphiti 社内検索Bot</h1>
        <div style={styles.tabs}>
          <button
            onClick={() => setActiveTab('chat')}
            style={{
              ...styles.tab,
              ...(activeTab === 'chat' && styles.activeTab),
            }}
          >
            💬 チャット
          </button>
          <button
            onClick={() => setActiveTab('search')}
            style={{
              ...styles.tab,
              ...(activeTab === 'search' && styles.activeTab),
            }}
          >
            🔍 検索
          </button>
        </div>
      </header>

      <main style={styles.main}>
        {activeTab === 'chat' ? <ChatInterface /> : <ManualSearch />}
      </main>

      <footer style={styles.footer}>
        <p>Powered by Graphiti + LangChain + React</p>
      </footer>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  app: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#1976d2',
    color: 'white',
    padding: '16px 24px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  headerTitle: {
    margin: '0 0 12px 0',
    fontSize: '28px',
    fontWeight: 'bold',
  },
  tabs: {
    display: 'flex',
    gap: '8px',
  },
  tab: {
    padding: '8px 20px',
    backgroundColor: 'rgba(255,255,255,0.2)',
    border: 'none',
    borderRadius: '4px 4px 0 0',
    color: 'white',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
  },
  activeTab: {
    backgroundColor: '#fff',
    color: '#1976d2',
  },
  main: {
    flex: 1,
    overflow: 'hidden',
  },
  footer: {
    backgroundColor: '#333',
    color: '#ccc',
    textAlign: 'center',
    padding: '12px',
    fontSize: '13px',
  },
};

export default App;

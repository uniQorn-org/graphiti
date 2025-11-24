/**
 * チャットインターフェース
 */
import React, { useState } from 'react';
import { chatAPI, ChatMessage, SearchResult } from '../services/api';
import SearchResults from './SearchResults';

const ChatInterface: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult | null>(null);
  const [sources, setSources] = useState<string[]>([]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await chatAPI.sendMessage({
        message: input,
        history: messages,
        include_search_results: true,
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setSearchResults(response.search_results || null);
      setSources(response.sources);
    } catch (error) {
      console.error('チャットエラー:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'エラーが発生しました。もう一度お試しください。',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.chatSection}>
        <h2 style={styles.title}>社内検索チャット</h2>

        {/* メッセージ履歴 */}
        <div style={styles.messagesContainer}>
          {messages.map((msg, index) => (
            <div
              key={index}
              style={{
                ...styles.message,
                ...(msg.role === 'user' ? styles.userMessage : styles.assistantMessage),
              }}
            >
              <div style={styles.messageRole}>
                {msg.role === 'user' ? '👤 あなた' : '🤖 Bot'}
              </div>
              <div style={styles.messageContent}>{msg.content}</div>
            </div>
          ))}
          {isLoading && (
            <div style={styles.loadingMessage}>
              <div style={styles.messageRole}>🤖 Bot</div>
              <div style={styles.messageContent}>考え中...</div>
            </div>
          )}
        </div>

        {/* 入力エリア */}
        <div style={styles.inputContainer}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="質問を入力してください..."
            style={styles.textarea}
            rows={3}
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={!input.trim() || isLoading}
            style={{
              ...styles.sendButton,
              ...((!input.trim() || isLoading) && styles.sendButtonDisabled),
            }}
          >
            送信
          </button>
        </div>
      </div>

      {/* 検索結果 */}
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
    display: 'flex',
    gap: '20px',
    height: '100%',
    padding: '20px',
  },
  chatSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
  },
  resultsSection: {
    flex: 1,
    maxWidth: '600px',
  },
  title: {
    margin: '0 0 20px 0',
    fontSize: '24px',
    fontWeight: 'bold',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    marginBottom: '20px',
    padding: '10px',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
  },
  message: {
    marginBottom: '15px',
    padding: '12px',
    borderRadius: '8px',
  },
  userMessage: {
    backgroundColor: '#e3f2fd',
    marginLeft: '20%',
  },
  assistantMessage: {
    backgroundColor: '#f5f5f5',
    marginRight: '20%',
  },
  loadingMessage: {
    padding: '12px',
    borderRadius: '8px',
    backgroundColor: '#f5f5f5',
    marginRight: '20%',
  },
  messageRole: {
    fontWeight: 'bold',
    marginBottom: '5px',
    fontSize: '14px',
  },
  messageContent: {
    whiteSpace: 'pre-wrap',
    lineHeight: '1.5',
  },
  inputContainer: {
    display: 'flex',
    gap: '10px',
  },
  textarea: {
    flex: 1,
    padding: '12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'none',
  },
  sendButton: {
    padding: '12px 24px',
    backgroundColor: '#1976d2',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  sendButtonDisabled: {
    backgroundColor: '#ccc',
    cursor: 'not-allowed',
  },
};

export default ChatInterface;

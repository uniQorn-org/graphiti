/**
 * 検索結果表示コンポーネント
 */
import React, { useState, useEffect } from 'react';
import { SearchResult, EntityEdge, factsAPI, episodesAPI } from '../services/api';
import FactEditor from './FactEditor';
import { useToast } from './ToastContainer';

interface SearchResultsProps {
  results: SearchResult;
}

const SearchResults: React.FC<SearchResultsProps> = ({ results }) => {
  const [editingEdge, setEditingEdge] = useState<EntityEdge | null>(null);
  const [localEdges, setLocalEdges] = useState<EntityEdge[]>(results.edges);
  const { showToast } = useToast();

  // resultsが変わったらlocalEdgesを更新
  useEffect(() => {
    setLocalEdges(results.edges);
  }, [results]);

  const handleEditFact = (edge: EntityEdge) => {
    setEditingEdge(edge);
  };

  const handleSaveFact = async (edgeUuid: string, newFact: string, reason?: string) => {
    try {
      const response = await factsAPI.updateFact(edgeUuid, {
        fact: newFact,
        attributes: reason ? { update_reason: reason } : undefined
      });

      if (response.status === 'updated') {
        // ローカル状態を更新: 古いfactを削除し、新しいfactを追加
        setLocalEdges((prev) => {
          const filtered = prev.filter((e) => e.uuid !== edgeUuid);

          // 新しいedgeがレスポンスに含まれている場合は追加
          if (response.new_edge) {
            return [...filtered, response.new_edge];
          }

          // 含まれていない場合は削除のみ（後方互換性のため）
          return filtered;
        });
        setEditingEdge(null);

        // Citations情報があれば表示
        const citationsInfo = response.new_edge?.citations?.length
          ? `\n📚 ソース: ${response.new_edge.citations.length}件のリンクを保持`
          : '';
        showToast(`Factを更新しました！\n旧UUID: ${response.old_uuid}\n新UUID: ${response.new_uuid}${citationsInfo}`, 'success');
      } else {
        showToast(`更新に失敗しました: ${response.message}`, 'error');
      }
    } catch (error: any) {
      console.error('Fact更新エラー:', error);
      const errorMsg = error.response?.data?.message || error.message || 'エラーが発生しました';
      showToast(`更新に失敗しました: ${errorMsg}`, 'error');
    }
  };

  const handleCancelEdit = () => {
    setEditingEdge(null);
  };

  const handleDeleteFact = async (edge: EntityEdge) => {
    if (!window.confirm(`このFactを削除してよろしいですか？\n\n${edge.fact}`)) {
      return;
    }

    try {
      // EdgeはEpisodeに紐づいているため、citationsまたはepisodesから関連するepisode_uuidを取得して削除
      let episodeUuid: string | null = null;

      // 1. citationsから取得を試みる
      if (edge.citations && edge.citations.length > 0) {
        episodeUuid = edge.citations[0].episode_uuid;
      }
      // 2. citationsがない場合はepisodes配列から取得
      else if (edge.episodes && edge.episodes.length > 0) {
        episodeUuid = edge.episodes[0];
      }

      if (!episodeUuid) {
        showToast(`削除に失敗しました: エピソード情報が見つかりません`, 'error');
        return;
      }

      const response = await episodesAPI.deleteEpisode(episodeUuid);

      if (response.status === 'deleted') {
        // ローカル状態から削除
        setLocalEdges((prev) => prev.filter((e) => e.uuid !== edge.uuid));
        showToast(`Fact（およびエピソード）を削除しました！`, 'success');
      } else {
        showToast(`削除に失敗しました: ${response.message}`, 'error');
      }
    } catch (error: any) {
      console.error('Fact削除エラー:', error);
      const errorMsg = error.response?.data?.message || error.message || 'エラーが発生しました';
      showToast(`削除に失敗しました: ${errorMsg}`, 'error');
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>検索結果</h2>

      {results.total_count === 0 ? (
        <div style={styles.noResults}>検索結果がありません</div>
      ) : (
        <>
          {/* エッジ（関係性）の表示 */}
          {localEdges.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>
                関連する事実 ({localEdges.length}件)
              </h3>
              {localEdges.map((edge) => (
                <div
                  key={edge.uuid}
                  style={{
                    ...styles.edgeCard,
                    ...(edge.updated_at && styles.edgeCardEdited),
                  }}
                >
                  {edge.updated_at && (
                    <div style={styles.editedBadge}>📝 修正済み</div>
                  )}
                  <div style={styles.edgeName}>{edge.name}</div>
                  <div style={styles.edgeFact}>{edge.fact}</div>

                  <div style={styles.metaContainer}>
                    {edge.valid_at && (
                      <div style={styles.edgeMeta}>
                        📅 出来事の日時: {new Date(edge.valid_at).toLocaleDateString('ja-JP', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </div>
                    )}
                    {edge.updated_at && (
                      <div style={styles.edgeMeta}>
                        🕒 最終更新: {new Date(edge.updated_at).toLocaleString('ja-JP', {
                          year: 'numeric',
                          month: 'numeric',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    )}
                    {edge.citations && edge.citations.length > 0 && (
                      <div style={styles.citationsContainer}>
                        <div style={styles.citationsTitle}>📚 ソース:</div>
                        {edge.citations.map((citation, idx) => (
                          <div key={idx} style={styles.citation}>
                            {citation.source_url ? (
                              <a
                                href={citation.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={styles.citationLink}
                              >
                                🔗 {citation.episode_name}
                              </a>
                            ) : (
                              <span style={styles.citationText}>
                                📄 {citation.episode_name}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {edge.original_fact && edge.original_fact !== edge.fact && (
                      <details style={styles.originalFactDetails}>
                        <summary style={styles.originalFactSummary}>
                          元の内容を表示
                        </summary>
                        <div style={styles.originalFactContent}>
                          {edge.original_fact}
                        </div>
                      </details>
                    )}
                  </div>

                  <div style={styles.buttonContainer}>
                    <button
                      onClick={() => handleEditFact(edge)}
                      style={styles.editButton}
                    >
                      ✏️ 修正
                    </button>
                    <button
                      onClick={() => handleDeleteFact(edge)}
                      style={styles.deleteButton}
                    >
                      🗑️ 削除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ノード（エンティティ）の表示 */}
          {results.nodes.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>
                関連するエンティティ ({results.nodes.length}件)
              </h3>
              {results.nodes.map((node) => (
                <div key={node.uuid} style={styles.nodeCard}>
                  <div style={styles.nodeName}>{node.name}</div>
                  {node.summary && (
                    <div style={styles.nodeSummary}>{node.summary}</div>
                  )}
                  {node.labels.length > 0 && (
                    <div style={styles.nodeLabels}>
                      {node.labels.map((label, idx) => (
                        <span key={idx} style={styles.label}>
                          {label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Fact編集モーダル */}
      {editingEdge && (
        <FactEditor
          edge={editingEdge}
          onSave={handleSaveFact}
          onCancel={handleCancelEdit}
        />
      )}
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '20px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    height: '100%',
    overflowY: 'auto',
  },
  title: {
    margin: '0 0 20px 0',
    fontSize: '20px',
    fontWeight: 'bold',
  },
  noResults: {
    textAlign: 'center',
    color: '#999',
    padding: '40px 20px',
  },
  section: {
    marginBottom: '30px',
  },
  sectionTitle: {
    fontSize: '16px',
    fontWeight: 'bold',
    marginBottom: '12px',
    color: '#333',
  },
  edgeCard: {
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    padding: '12px',
    marginBottom: '10px',
    backgroundColor: '#fafafa',
    position: 'relative',
  },
  edgeCardEdited: {
    backgroundColor: '#fffbf0',
    borderColor: '#ffa726',
    borderWidth: '2px',
  },
  editedBadge: {
    position: 'absolute',
    top: '8px',
    right: '8px',
    backgroundColor: '#ffa726',
    color: 'white',
    padding: '3px 8px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 'bold',
  },
  edgeName: {
    fontWeight: 'bold',
    color: '#1976d2',
    marginBottom: '8px',
    fontSize: '14px',
  },
  edgeFact: {
    marginBottom: '12px',
    lineHeight: '1.5',
    fontSize: '14px',
  },
  metaContainer: {
    marginBottom: '12px',
  },
  edgeMeta: {
    fontSize: '12px',
    color: '#666',
    marginBottom: '4px',
  },
  originalFactDetails: {
    marginTop: '8px',
    fontSize: '12px',
  },
  originalFactSummary: {
    cursor: 'pointer',
    color: '#1976d2',
    userSelect: 'none',
    fontSize: '12px',
  },
  originalFactContent: {
    marginTop: '6px',
    padding: '8px',
    backgroundColor: '#f0f0f0',
    borderRadius: '4px',
    fontSize: '13px',
    color: '#555',
    borderLeft: '3px solid #1976d2',
  },
  citationsContainer: {
    marginTop: '8px',
    padding: '8px',
    backgroundColor: '#f5f9ff',
    borderRadius: '4px',
    borderLeft: '3px solid #2196f3',
  },
  citationsTitle: {
    fontSize: '12px',
    fontWeight: 'bold',
    color: '#1976d2',
    marginBottom: '6px',
  },
  citation: {
    marginBottom: '4px',
  },
  citationLink: {
    fontSize: '12px',
    color: '#1976d2',
    textDecoration: 'none',
    display: 'inline-block',
    padding: '2px 0',
    transition: 'color 0.2s',
  },
  citationText: {
    fontSize: '12px',
    color: '#666',
  },
  buttonContainer: {
    display: 'flex',
    gap: '8px',
    marginTop: '4px',
  },
  editButton: {
    padding: '6px 12px',
    backgroundColor: '#4caf50',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '13px',
  },
  deleteButton: {
    padding: '6px 12px',
    backgroundColor: '#f44336',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '13px',
  },
  nodeCard: {
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    padding: '12px',
    marginBottom: '10px',
    backgroundColor: '#f9f9f9',
  },
  nodeName: {
    fontWeight: 'bold',
    color: '#333',
    marginBottom: '8px',
    fontSize: '15px',
  },
  nodeSummary: {
    marginBottom: '8px',
    lineHeight: '1.5',
    fontSize: '13px',
    color: '#555',
  },
  nodeLabels: {
    display: 'flex',
    gap: '5px',
    flexWrap: 'wrap',
  },
  label: {
    padding: '3px 8px',
    backgroundColor: '#e3f2fd',
    borderRadius: '3px',
    fontSize: '11px',
    color: '#1976d2',
  },
};

export default SearchResults;

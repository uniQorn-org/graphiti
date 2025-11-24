/**
 * Fact編集モーダル
 */
import React, { useState } from 'react';
import { EntityEdge } from '../services/api';
import { useToast } from './ToastContainer';

interface FactEditorProps {
  edge: EntityEdge;
  onSave: (edgeUuid: string, newFact: string, reason?: string) => void;
  onCancel: () => void;
}

const FactEditor: React.FC<FactEditorProps> = ({ edge, onSave, onCancel }) => {
  const [newFact, setNewFact] = useState(edge.fact);
  const [reason, setReason] = useState('');
  const { showToast } = useToast();

  const handleSave = () => {
    if (!newFact.trim()) {
      showToast('Factを入力してください', 'error');
      return;
    }
    onSave(edge.uuid, newFact, reason || undefined);
  };

  return (
    <div style={styles.overlay} onClick={onCancel}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h3 style={styles.title}>Factを編集</h3>

        <div style={styles.field}>
          <label style={styles.label}>関係性タイプ:</label>
          <div style={styles.readOnly}>{edge.name}</div>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>現在のFact:</label>
          <div style={styles.originalFact}>{edge.fact}</div>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>新しいFact: *</label>
          <textarea
            value={newFact}
            onChange={(e) => setNewFact(e.target.value)}
            style={styles.textarea}
            rows={4}
            placeholder="修正後のFactを入力..."
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>修正理由:</label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            style={styles.input}
            placeholder="修正理由を入力（任意）"
          />
        </div>

        <div style={styles.actions}>
          <button onClick={onCancel} style={styles.cancelButton}>
            キャンセル
          </button>
          <button onClick={handleSave} style={styles.saveButton}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modal: {
    backgroundColor: 'white',
    borderRadius: '8px',
    padding: '24px',
    maxWidth: '600px',
    width: '90%',
    maxHeight: '90vh',
    overflowY: 'auto',
    boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
  },
  title: {
    margin: '0 0 20px 0',
    fontSize: '20px',
    fontWeight: 'bold',
  },
  field: {
    marginBottom: '16px',
  },
  label: {
    display: 'block',
    marginBottom: '6px',
    fontWeight: 'bold',
    fontSize: '14px',
  },
  readOnly: {
    padding: '8px 12px',
    backgroundColor: '#f5f5f5',
    borderRadius: '4px',
    fontSize: '14px',
  },
  originalFact: {
    padding: '8px 12px',
    backgroundColor: '#fff3e0',
    borderRadius: '4px',
    fontSize: '14px',
    border: '1px solid #ffe0b2',
  },
  textarea: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'vertical',
  },
  input: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
  },
  actions: {
    display: 'flex',
    gap: '10px',
    justifyContent: 'flex-end',
    marginTop: '20px',
  },
  cancelButton: {
    padding: '10px 20px',
    backgroundColor: '#f5f5f5',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  saveButton: {
    padding: '10px 20px',
    backgroundColor: '#4caf50',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold',
  },
};

export default FactEditor;

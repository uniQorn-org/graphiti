/**
 * Toast通知コンポーネント
 */
import React, { useEffect, useState } from 'react';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  message: string;
  type: ToastType;
  duration?: number;
  onClose: () => void;
}

const Toast: React.FC<ToastProps> = ({ message, type, duration = 3000, onClose }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onClose, 300); // Wait for fade out animation
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const getBackgroundColor = () => {
    switch (type) {
      case 'success':
        return '#4caf50';
      case 'error':
        return '#f44336';
      case 'info':
        return '#2196f3';
      default:
        return '#333';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✕';
      case 'info':
        return 'ℹ';
      default:
        return '';
    }
  };

  return (
    <div
      style={{
        ...styles.toast,
        backgroundColor: getBackgroundColor(),
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(-20px)',
      }}
    >
      <span style={styles.icon}>{getIcon()}</span>
      <span style={styles.message}>{message}</span>
      <button onClick={() => { setIsVisible(false); setTimeout(onClose, 300); }} style={styles.closeButton}>
        ×
      </button>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  toast: {
    position: 'fixed',
    top: '20px',
    right: '20px',
    padding: '16px 24px',
    borderRadius: '8px',
    color: 'white',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
    zIndex: 9999,
    minWidth: '300px',
    maxWidth: '500px',
    transition: 'opacity 0.3s, transform 0.3s',
    fontFamily: 'sans-serif',
  },
  icon: {
    fontSize: '20px',
    fontWeight: 'bold',
  },
  message: {
    flex: 1,
    fontSize: '14px',
    lineHeight: '1.5',
    whiteSpace: 'pre-line',
  },
  closeButton: {
    background: 'none',
    border: 'none',
    color: 'white',
    fontSize: '24px',
    cursor: 'pointer',
    padding: '0',
    marginLeft: '8px',
    opacity: 0.8,
    lineHeight: '1',
  },
};

export default Toast;

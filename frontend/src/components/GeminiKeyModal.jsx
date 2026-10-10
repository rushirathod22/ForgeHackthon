import React, { useState, useEffect } from 'react';
import { Sparkles, Key, Check, AlertCircle, X, ExternalLink, ShieldCheck, Loader2 } from 'lucide-react';
import { apiUrl } from '../api';

export function GeminiKeyModal({ isOpen, onClose, onKeySaved }) {
  const [apiKey, setApiKey] = useState('');
  const [isConfigured, setIsConfigured] = useState(false);
  const [maskedKey, setMaskedKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null); // { type: 'success' | 'error', text: string }

  // Load current status
  useEffect(() => {
    if (!isOpen) return;
    setStatusMsg(null);
    fetch(apiUrl('/api/v1/config/gemini'))
      .then((res) => res.json())
      .then((data) => {
        setIsConfigured(data.configured || false);
        setMaskedKey(data.masked_key || '');
      })
      .catch(() => {});
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) return;
    setLoading(true);
    setStatusMsg(null);

    try {
      const res = await fetch(apiUrl('/api/v1/config/gemini'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to validate Gemini API key');
      }

      setIsConfigured(true);
      setMaskedKey(data.masked_key);
      setApiKey('');
      setStatusMsg({ type: 'success', text: '✓ Gemini API key saved! Visual attribute tagging is now active.' });
      if (onKeySaved) onKeySaved(true);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message || 'Failed to save key' });
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async () => {
    setLoading(true);
    try {
      await fetch(apiUrl('/api/v1/config/gemini'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: '' }),
      });
      setIsConfigured(false);
      setMaskedKey('');
      setApiKey('');
      setStatusMsg({ type: 'success', text: 'Gemini API key removed. Reverted to HSV heuristic detection.' });
      if (onKeySaved) onKeySaved(false);
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(2, 6, 23, 0.85)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px',
    }}>
      <div style={{
        background: '#0f172a',
        border: '1px solid rgba(6, 182, 212, 0.3)',
        borderRadius: '16px',
        padding: '28px',
        maxWidth: '520px',
        width: '100%',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(6, 182, 212, 0.15)',
        color: '#f8fafc',
        position: 'relative',
      }}>
        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '18px',
            right: '18px',
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            cursor: 'pointer',
          }}
        >
          <X size={20} />
        </button>

        {/* Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
          <div style={{
            background: 'rgba(6, 182, 212, 0.15)',
            border: '1px solid rgba(6, 182, 212, 0.4)',
            padding: '8px',
            borderRadius: '10px',
            color: '#22d3ee',
          }}>
            <Sparkles size={22} />
          </div>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>Google Gemini Vision</h3>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>AI-Powered Person Attribute Extraction</p>
          </div>
        </div>

        <p style={{ fontSize: '0.88rem', color: '#cbd5e1', lineHeight: '1.5', marginBottom: '20px' }}>
          Connect your Google Gemini API key to accurately detect visual person attributes in CCTV footage:
          <strong> shirt & pants colors</strong>, <strong>holding phone</strong>, <strong>wearing backpack/bag</strong>, and <strong>age/gender estimates</strong>.
        </p>

        {/* Active Status Badge */}
        {isConfigured ? (
          <div style={{
            background: 'rgba(16, 185, 129, 0.12)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '10px',
            padding: '12px 16px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShieldCheck size={20} color="#10b981" />
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#34d399' }}>Gemini 3.6 Flash Active</div>
                <div style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#94a3b8' }}>Key: {maskedKey}</div>
              </div>
            </div>
            <button
              onClick={handleRemove}
              disabled={loading}
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '0.75rem',
                cursor: 'pointer',
              }}
            >
              Remove
            </button>
          </div>
        ) : (
          <div style={{
            background: 'rgba(245, 158, 11, 0.1)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: '10px',
            padding: '10px 14px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '0.82rem',
            color: '#fbbf24',
          }}>
            <Key size={18} />
            <span>No API key set. The system currently falls back to HSV color heuristics.</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSave}>
          <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '8px' }}>
            {isConfigured ? 'Update Gemini API Key:' : 'Enter Gemini API Key:'}
          </label>
          <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
            <input
              type="password"
              placeholder="AIzaSy..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              style={{
                flex: 1,
                background: '#020617',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '10px 14px',
                color: '#f8fafc',
                fontSize: '0.9rem',
                fontFamily: 'monospace',
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={loading || !apiKey.trim()}
              style={{
                background: apiKey.trim() ? '#06b6d4' : '#334155',
                color: apiKey.trim() ? '#020617' : '#94a3b8',
                border: 'none',
                borderRadius: '8px',
                padding: '0 18px',
                fontWeight: 700,
                fontSize: '0.85rem',
                cursor: apiKey.trim() ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
              Save
            </button>
          </div>
        </form>

        {statusMsg && (
          <div style={{
            padding: '10px 14px',
            borderRadius: '8px',
            fontSize: '0.82rem',
            marginBottom: '16px',
            background: statusMsg.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${statusMsg.type === 'success' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'}`,
            color: statusMsg.type === 'success' ? '#34d399' : '#f87171',
          }}>
            {statusMsg.text}
          </div>
        )}

        {/* Help Link */}
        <div style={{
          borderTop: '1px solid #1e293b',
          paddingTop: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.78rem',
          color: '#64748b',
        }}>
          <span>Need a free Gemini API key?</span>
          <a
            href="https://aistudio.google.com/app/apikey"
            target="_blank"
            rel="noreferrer"
            style={{
              color: '#38bdf8',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontWeight: 600,
            }}
          >
            Google AI Studio <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </div>
  );
}

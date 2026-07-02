import React, { useEffect, useState, useRef } from 'react';
import { api } from '../../lib/api';
import { LuBot, LuSend, LuTriangleAlert, LuInfo, LuUser, LuSettings, LuCopy, LuLoader } from 'react-icons/lu';

export default function Chat() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [ollamaOk, setOllamaOk] = useState(true);
  const [messages, setMessages] = useState([]);
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    api.get('/api/dashboard/init')
      .then(res => {
        const m = res.data.models || [];
        setModels(m);
        if (m.length > 0) {
          const firstModel = m[0].id;
          setSelectedModel(firstModel);
          setOllamaOk(!firstModel.startsWith('error:'));
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!selectedModel || !inputMessage.trim() || loading) return;

    const userText = inputMessage.trim();
    setInputMessage('');
    
    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    setLoading(true);

    try {
      const res = await api.post('/api/chat', {
        model: selectedModel,
        message: userText
      });
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: res.data.message || 'Sin respuesta',
        usage: res.data.usage,
        latency: res.data.latency_ms
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        error: true,
        content: err.response?.data?.detail || err.message || 'Error al conectar con el servidor'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  // Helper to render markdown-like code blocks
  const renderContent = (content) => {
    if (!content) return null;
    const parts = content.split(/(```[\w]*\n[\s\S]*?```)/g);
    
    return parts.map((part, idx) => {
      if (part.startsWith('```')) {
        const match = part.match(/```([\w]*)\n([\s\S]*?)```/);
        const lang = match ? match[1] : '';
        const code = match ? match[2] : part.replace(/```/g, '');
        return (
          <div key={idx} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', margin: '1rem 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 1rem', background: 'var(--panel-bg)', borderBottom: '1px solid var(--border)', fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              <span>{lang || 'CODE'}</span>
              <button 
                onClick={() => copyToClipboard(code.trim())}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
              >
                <LuCopy size={14} /> Copy
              </button>
            </div>
            <pre style={{ margin: 0, padding: '1rem', background: 'var(--bg-color)', overflowX: 'auto', fontSize: '0.85rem', fontFamily: '"JetBrains Mono", monospace' }}>
              <code>{code.trim()}</code>
            </pre>
          </div>
        );
      }
      return <p key={idx} style={{ margin: '0 0 0.5rem 0', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{part}</p>;
    });
  };

  return (
    <div id="chat" className="section-content active" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      
      {/* Header matching the screenshot */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '1rem', borderBottom: '1px solid var(--border)', marginBottom: '1.5rem', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>Interactive Chat Test</h2>
          {ollamaOk ? (
            <span className="badge badge-active" style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}>● Connected</span>
          ) : (
            <span className="badge" style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', background: '#451a1a', color: '#fca5a5', border: '1px solid #7f1d1d' }}>● Disconnected</span>
          )}
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>MODEL:</span>
            <select 
              value={selectedModel}
              onChange={(e) => {
                setSelectedModel(e.target.value);
                setOllamaOk(!e.target.value.startsWith('error:'));
              }}
              style={{ 
                padding: '0.35rem 0.75rem', 
                background: 'var(--panel-bg)', 
                border: '1px solid var(--border)', 
                color: '#fff', 
                borderRadius: 'var(--radius)',
                fontSize: '0.85rem',
                outline: 'none',
                minWidth: '200px'
              }}
            >
              {models.map((m, idx) => (
                <option key={idx} value={m.id}>{m.id}</option>
              ))}
            </select>
          </div>
          <LuSettings size={18} style={{ color: 'var(--text-muted)', cursor: 'pointer' }} />
        </div>
      </header>

      {/* Messages Area */}
      <div className="chat-messages" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingRight: '0.5rem' }}>
        
        {/* Persistent System Message */}
        <div className="message system" style={{ display: 'flex', gap: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem', alignItems: 'center', background: 'transparent' }}>
          <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'var(--panel-bg)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <LuInfo size={14} />
          </div>
          <div>System initialized. Connected to model '{selectedModel || 'llama-3-8b-instruct'}' on Local Cluster Node 01.</div>
        </div>

        {/* Dynamic Messages */}
        {messages.map((msg, idx) => {
          if (msg.role === 'user') {
            return (
              <div key={idx} className="message user" style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', alignItems: 'flex-start' }}>
                <div style={{ border: '1px solid var(--border)', padding: '1rem', borderRadius: 'var(--radius)', background: 'transparent', maxWidth: '85%', fontSize: '0.9rem', lineHeight: 1.5 }}>
                  {msg.content}
                </div>
                <div style={{ width: '32px', height: '32px', borderRadius: 'var(--radius)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <LuUser size={16} />
                </div>
              </div>
            );
          } else {
            return (
              <div key={idx} className="message assistant" style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                <div style={{ width: '32px', height: '32px', borderRadius: 'var(--radius)', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
                  <LuBot size={18} />
                </div>
                <div style={{ flex: 1, fontSize: '0.9rem', color: msg.error ? '#fca5a5' : '#fff' }}>
                  {renderContent(msg.content)}
                  {msg.usage && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Tokens: {msg.usage.total_tokens} | Latencia: {msg.latency} ms
                    </div>
                  )}
                </div>
              </div>
            );
          }
        })}

        {loading && (
          <div className="message assistant" style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: 'var(--radius)', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', flexShrink: 0 }}>
              <LuBot size={18} />
            </div>
            <div style={{ flex: 1, fontSize: '0.9rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', height: '32px' }}>
              <LuLoader className="spinner" size={16} style={{ animation: 'spin 2s linear infinite' }} /> 
              Generando respuesta...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input" style={{ marginTop: '1.5rem', position: 'relative', flexShrink: 0 }}>
        <form onSubmit={handleSubmit} style={{ margin: 0 }}>
          <textarea 
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu prompt de prueba aquí (Shift+Enter para nueva línea)..."
            disabled={loading || !ollamaOk}
            style={{ 
              width: '100%', 
              background: 'var(--panel-bg)', 
              border: '1px solid var(--border)', 
              borderRadius: 'var(--radius)', 
              padding: '1rem', 
              paddingRight: '3rem',
              color: '#fff', 
              resize: 'none', 
              height: '80px',
              fontFamily: 'inherit',
              fontSize: '0.9rem',
              outline: 'none',
              boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
            }}
          />
          <button 
            type="submit" 
            disabled={loading || !inputMessage.trim() || !ollamaOk} 
            style={{ 
              position: 'absolute', 
              right: '1rem', 
              bottom: '1rem', 
              background: 'transparent', 
              border: 'none', 
              color: (inputMessage.trim() && !loading) ? 'var(--primary)' : 'var(--text-muted)', 
              cursor: (inputMessage.trim() && !loading) ? 'pointer' : 'not-allowed',
              transition: 'color 0.2s',
              display: 'flex',
              padding: '0.25rem'
            }}
          >
            <LuSend size={20} />
          </button>
        </form>
        
        {/* CSS for spinner animation */}
        <style>{`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );
}

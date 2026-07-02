import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { LuKeyRound, LuEye, LuCopy, LuX, LuTriangleAlert, LuRotateCw, LuCheck } from 'react-icons/lu';

export default function Keys() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState('');
  const [keyName, setKeyName] = useState('');
  const [newKey, setNewKey] = useState(null);
  
  // Modals state
  const [selectedKeyDetails, setSelectedKeyDetails] = useState(null);
  const [regenConfirmOpen, setRegenConfirmOpen] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [regenLoading, setRegenLoading] = useState(false);

  const fetchKeys = async () => {
    try {
      const res = await api.get('/api/dashboard/init');
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchKeys();
  }, []);

  const handleModelChange = (e) => {
    const val = e.target.value;
    setSelectedModel(val);
    setKeyName(val);
  };

  const handleGenerateKey = async (e) => {
    e.preventDefault();
    if (!selectedModel) return;
    try {
      const res = await api.post('/api/keys', {
        name: keyName,
        model: selectedModel
      });
      setNewKey(res.data.api_key);
      setKeyName('');
      setSelectedModel('');
      fetchKeys();
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al generar la clave');
    }
  };

  const handleCopy = async (text) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-999999px';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        ta.remove();
      }
      alert('Copiado al portapapeles');
    } catch (err) {
      console.error(err);
    }
  };

  const executeRegen = async () => {
    if (confirmInput !== 'REGENERAR') return;
    setRegenLoading(true);
    try {
      const res = await api.post('/api/auth/api-key/regenerate');
      setRegenConfirmOpen(false);
      setConfirmInput('');
      alert('API Key regenerada exitosamente. Recargando claves...');
      fetchKeys();
    } catch (e) {
      alert(e.response?.data?.detail || 'Error al regenerar');
    } finally {
      setRegenLoading(false);
    }
  };

  if (loading) {
    return <div className="muted" style={{ padding: '2rem' }}>Cargando API Keys...</div>;
  }

  const { keys = [], models = [] } = data || {};
  const availableModels = models.filter(m => !String(m.id || '').startsWith('error:'));

  const formatDate = (v) => {
    if (!v) return '-';
    return v.substring(0, 19).replace('T', ' ');
  };

  return (
    <div id="keys" className="section-content active">
      <section className="panel">
        <h2><LuKeyRound /> API Keys</h2>
        <p className="muted" style={{ marginBottom: '1.5rem' }}>
          Manage credentials for programmatic access to the cluster.
        </p>
        <form onSubmit={handleGenerateKey} style={{ maxWidth: '500px' }}>
          <label htmlFor="key-model">Modelo</label>
          <select 
            id="key-model" 
            required 
            value={selectedModel} 
            onChange={handleModelChange}
            style={{ marginBottom: '0.75rem' }}
          >
            <option value="" disabled>Seleccionar modelo</option>
            {availableModels.map((m, idx) => (
              <option key={idx} value={m.id}>{m.id}</option>
            ))}
          </select>

          <label htmlFor="key-name">Nombre de la key</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input 
              id="key-name" 
              type="text" 
              required 
              placeholder="Ej: llama3.1:8b" 
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              style={{ marginBottom: 0 }}
            />
            <button type="submit" style={{ width: 'auto', marginBottom: 0 }}>Generar</button>
          </div>
        </form>

        {newKey && (
          <div id="new-key-container" style={{ marginTop: '1.5rem' }}>
            <p className="small" style={{ color: '#047857', fontWeight: 500, marginBottom: '0.5rem' }}>
              <LuCheck style={{ width: '16px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
              Key generada exitosamente. Cópiala ahora, no volverá a mostrarse completa.
            </p>
            <div className="key-display-box" style={{ margin: '1.25rem 0 0 0' }}>
              <code style={{ flex: 1, background: 'transparent', fontSize: '1rem', color: 'var(--text-main)' }}>{newKey}</code>
              <button 
                type="button" 
                onClick={() => handleCopy(newKey)} 
                className="secondary"
                style={{ width: 'auto', padding: '0.5rem', margin: 0 }}
              >
                <LuCopy style={{ width: '16px' }} />
              </button>
            </div>
          </div>
        )}

        <h3 style={{ marginTop: '2rem', borderTop: '1px solid var(--border)', paddingTop: '1.5rem' }}>
          Keys existentes
          <button 
            type="button" 
            onClick={() => setRegenConfirmOpen(true)} 
            className="secondary"
            style={{ 
              float: 'right', 
              fontSize: '0.8rem', 
              padding: '0.4rem 0.75rem', 
              color: '#dc2626', 
              borderColor: '#fca5a5' 
            }}
            title="Desactiva la clave actual inmediatamente y genera una nueva para tu sesión"
          >
            <LuRotateCw style={{ width: '14px', marginRight: '4px', verticalAlign: 'middle' }} /> Regenerar activa
          </button>
        </h3>

        <ul className="keys-list">
          {keys && keys.length > 0 ? (
            keys.map((k, idx) => (
              <li key={idx}>
                <div>
                  <strong style={{ display: 'block', fontSize: '0.95rem' }}>{k.name}</strong>
                  {k.model ? (
                    <span 
                      className="badge badge-ok" 
                      style={{ border: 'none', fontSize: '0.75rem', marginRight: '4px' }}
                    >
                      Modelo: {k.model}
                    </span>
                  ) : (
                    <span 
                      className="badge badge-global" 
                      style={{ border: 'none', fontSize: '0.75rem', marginRight: '4px' }}
                    >
                      Global (todos los modelos)
                    </span>
                  )}
                  <span className={`badge badge-${k.status}`} style={{ fontSize: '0.75rem' }}>
                    {k.status}
                  </span>
                  <span className="small muted" style={{ display: 'block', marginTop: '4px' }}>
                    Creada: {k.created_at ? k.created_at.substring(0, 10) : '-'} | Expira: {k.expires_at ? k.expires_at.substring(0, 10) : 'No definido'}
                  </span>
                </div>
                <div className="key-actions">
                  <code>{k.masked_key}</code>
                  <button 
                    className="copy-btn" 
                    title="Copiar API Key"
                    onClick={() => handleCopy(k.raw_key || k.masked_key)}
                  >
                    <LuCopy style={{ width: '16px' }} />
                  </button>
                  <button 
                    className="copy-btn" 
                    title="Ver detalles"
                    onClick={() => setSelectedKeyDetails(k)}
                  >
                    <LuEye style={{ width: '16px' }} />
                  </button>
                </div>
              </li>
            ))
          ) : (
            <li className="muted">No hay keys generadas en la base de datos.</li>
          )}
        </ul>
      </section>

      {/* MODAL: VER DETALLES API KEY */}
      <div className={`modal-overlay ${selectedKeyDetails ? 'open' : ''}`} role="dialog" aria-modal="true">
        {selectedKeyDetails && (
          <div className="modal">
            <div className="modal-header">
              <h3><LuKeyRound style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Detalles de API Key</h3>
              <button className="modal-close" onClick={() => setSelectedKeyDetails(null)} aria-label="Cerrar">
                <LuX style={{ width: '16px' }} />
              </button>
            </div>
            <div className="modal-body">
              <div className="modal-info-row">
                <span>Estado</span>
                <span>
                  <span className={`badge badge-${selectedKeyDetails.status === 'active' ? 'active' : selectedKeyDetails.status === 'inactive' ? 'inactive' : 'archived'}`}>
                    {selectedKeyDetails.status}
                  </span>
                </span>
              </div>
              <div className="modal-info-row">
                <span>Nombre</span>
                <span>{selectedKeyDetails.name || '-'}</span>
              </div>
              <div className="modal-info-row">
                <span>Modelo vinculado</span>
                <span>{selectedKeyDetails.model || 'Global (todos los modelos)'}</span>
              </div>
              <div className="modal-info-row">
                <span>Creada</span>
                <span>{formatDate(selectedKeyDetails.created_at)}</span>
              </div>
              <div className="modal-info-row">
                <span>Expira</span>
                <span>{formatDate(selectedKeyDetails.expires_at)}</span>
              </div>
              <div className="modal-info-row">
                <span>Último acceso</span>
                <span>{formatDate(selectedKeyDetails.last_accessed)}</span>
              </div>
              <div className="modal-info-row">
                <span>Última IP</span>
                <span>{selectedKeyDetails.last_used_ip || '-'}</span>
              </div>
              <div className="modal-info-row">
                <span>Permisos</span>
                <span>{Array.isArray(selectedKeyDetails.scopes) ? selectedKeyDetails.scopes.join(', ') : (selectedKeyDetails.scopes || 'read, write')}</span>
              </div>
              <p style={{ fontSize: '0.85rem', fontWeight: 500, margin: '1rem 0 0.4rem' }}>Clave (enmascarada):</p>
              <div className="key-display-box" style={{ display: 'flex', alignItems: 'center' }}>
                <code style={{ flex: 1, background: 'transparent', wordBreak: 'break-all', color: 'var(--text-main)' }}>{selectedKeyDetails.masked_key}</code>
                <button 
                  type="button" 
                  className="copy-btn" 
                  onClick={() => handleCopy(selectedKeyDetails.raw_key || selectedKeyDetails.masked_key)}
                  title="Copiar"
                >
                  <LuCopy style={{ width: '16px' }} />
                </button>
              </div>
            </div>
            <div className="modal-footer">
              <button type="button" className="secondary" onClick={() => setSelectedKeyDetails(null)}>Cerrar</button>
              <button 
                type="button" 
                className="danger" 
                onClick={() => { setSelectedKeyDetails(null); setRegenConfirmOpen(true); }}
                style={{ fontSize: '0.88rem' }} 
                title="Desactiva la clave actual inmediatamente"
              >
                <LuRotateCw style={{ width: '14px', marginRight: '4px', verticalAlign: 'middle' }} /> Regenerar
              </button>
            </div>
          </div>
        )}
      </div>

      {/* MODAL: CONFIRMAR REGENERAR KEY */}
      <div className={`modal-overlay ${regenConfirmOpen ? 'open' : ''}`} role="dialog" aria-modal="true">
        <div className="modal">
          <div className="modal-header">
            <h3><LuTriangleAlert style={{ width: '18px', color: '#dc2626', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> ¿Regenerar API Key?</h3>
            <button className="modal-close" onClick={() => setRegenConfirmOpen(false)} aria-label="Cerrar">
              <LuX style={{ width: '16px' }} />
            </button>
          </div>
          <div className="modal-body">
            <div className="warning-box">
              <strong>Impacto inmediato</strong>
              <ul>
                <li>Tu clave actual quedará <strong>desactivada</strong> al instante.</li>
                <li>Todos los servicios conectados dejarán de funcionar.</li>
                <li>Deberás actualizar la clave en cada integración.</li>
                <li>Esta acción <strong>no se puede deshacer</strong>.</li>
              </ul>
            </div>
            <div className="confirm-input-wrap">
              <label htmlFor="regen-confirm-input">Escribe <strong>REGENERAR</strong> para confirmar:</label>
              <input 
                type="text" 
                id="regen-confirm-input" 
                placeholder="REGENERAR" 
                autoComplete="off" 
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
              />
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="secondary" onClick={() => setRegenConfirmOpen(false)}>Cancelar</button>
            <button 
              type="button" 
              className="danger" 
              id="regen-confirm-btn" 
              disabled={confirmInput !== 'REGENERAR' || regenLoading} 
              onClick={executeRegen}
            >
              <LuRotateCw style={{ width: '14px', marginRight: '4px', verticalAlign: 'middle' }} /> 
              {regenLoading ? 'Procesando...' : 'Regenerar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

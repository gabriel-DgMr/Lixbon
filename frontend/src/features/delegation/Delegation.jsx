import React, { useState } from 'react';
import { api } from '../../lib/api';
import { LuSparkles, LuBrainCircuit } from 'react-icons/lu';

export default function Delegation() {
  const [userInput, setUserInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!userInput.trim()) return;

    setLoading(true);
    setResult({
      status: 'Procesando... (embedding → clasificación → enrutamiento → ejecución)'
    });

    try {
      const res = await api.post('/api/delegate', { user_input: userInput });
      setResult(res.data);
    } catch (err) {
      setResult({
        error: err.response?.data?.detail || err.message || 'Error al conectar con el servidor'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div id="delegate" className="section-content active">
      <section className="panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <h2><LuSparkles style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Delegación Inteligente</h2>
        <p className="muted">
          Escribe tu solicitud en lenguaje natural. El sistema la clasifica automáticamente, busca
          contexto similar en tu historial y la delega al modelo Ollama más adecuado.
        </p>

        <form onSubmit={handleSubmit} style={{ marginTop: '1.25rem' }}>
          <label htmlFor="delegate-input">¿Qué necesitas hacer?</label>
          <textarea 
            id="delegate-input" 
            rows="3" 
            required
            placeholder="Ej: Necesito desplegar mi app, mi API devuelve error 500, ¿cómo configuro variables de entorno?..."
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
          ></textarea>
          <button type="submit" disabled={loading}>
            <LuBrainCircuit style={{ width: '18px', marginRight: '4px', verticalAlign: 'middle' }} /> 
            {loading ? 'Delegando...' : 'Delegar solicitud'}
          </button>
        </form>

        {result && (
          <div id="delegate-result-box" style={{ marginTop: '1.5rem' }}>
            {result.status && (
              <div className="muted small" style={{ marginBottom: '1rem' }}>{result.status}</div>
            )}
            
            {result.error && (
              <div className="error-box" style={{ marginBottom: '1rem' }}>{result.error}</div>
            )}

            {result.classification && (
              <div className="classification-tags">
                {result.routing?.type && (
                  <span className={`tag tag-router-${result.routing.type}`}>
                    {result.routing.type}
                  </span>
                )}
                {result.classification.intent && (
                  <span className="tag">intent: {result.classification.intent}</span>
                )}
                {result.classification.complexity != null && (
                  <span className="tag">complejidad: {result.classification.complexity}</span>
                )}
                {result.classification.domain && (
                  <span className="tag">dominio: {result.classification.domain}</span>
                )}
                {result.classification.riskLevel && (
                  <span className="tag">riesgo: {result.classification.riskLevel}</span>
                )}
                {result.routing?.model && (
                  <span className="tag">modelo: {result.routing.model}</span>
                )}
              </div>
            )}

            {result.response && (
              <div className="delegate-result" style={{ background: 'var(--bg-color)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem 1.25rem', whiteSpace: 'pre-wrap' }}>
                {result.response}
              </div>
            )}

            {result.execution_time_ms != null && (
              <p className="small muted" style={{ marginTop: '0.5rem', textAlign: 'right' }}>
                Tiempo: {result.execution_time_ms} ms
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

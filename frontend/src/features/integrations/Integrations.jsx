import React from 'react';
import { LuBlocks, LuTerminal, LuWorkflow, LuCode } from 'react-icons/lu';

export default function Integrations() {
  return (
    <div id="integrations" className="section-content active">
      <section className="panel">
        <h2><LuBlocks style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Integraciones API</h2>
        <p className="muted">
          El Gateway es 100% compatible con el formato de API de OpenAI.
        </p>

        <div className="integration-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginTop: '1.5rem' }}>
          <article className="quick-card" style={{ padding: '1.5rem' }}>
            <h3>
              <LuTerminal style={{ width: '18px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> 
              curl (Terminal)
            </h3>
            <pre style={{ marginTop: '0.75rem', fontSize: '0.8rem', background: '#0e0e11', border: '1px solid var(--border)' }}>
<code>{`curl -X POST "http://IP_SERVIDOR:8000/v1/chat/completions" \\
  -H "Authorization: Bearer TU_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model":"llama3.1:8b",
    "messages":[{"role":"user","content":"Hola"}],
    "client_id":"pc-diseno-01"
  }'`}</code>
            </pre>
          </article>

          <article className="quick-card" style={{ padding: '1.5rem' }}>
            <h3>
              <LuWorkflow style={{ width: '18px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> 
              n8n / Make
            </h3>
            <ul style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'inside' }}>
              <li><strong>Nodo:</strong> OpenAI Chat Model</li>
              <li><strong>Base URL:</strong> <code>http://IP_SERVIDOR:8000/v1</code></li>
              <li><strong>API Key:</strong> Generada en este panel</li>
              <li><strong>Model:</strong> El nombre exacto de Ollama (ej: <code>llama3.1:8b</code>)</li>
            </ul>
          </article>

          <article className="quick-card" style={{ padding: '1.5rem', gridColumn: 'span 1' }}>
            <h3>
              <LuCode style={{ width: '18px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> 
              Node.js / Python SDK
            </h3>
            <ul style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'inside' }}>
              <li>Instancia el cliente oficial de OpenAI en tu código.</li>
              <li>Cambia <code>baseURL</code> apuntando al puerto 8000 del servidor.</li>
              <li>Añade el header <code>client_id</code> si deseas separar las métricas por aplicación o equipo.</li>
            </ul>
          </article>
        </div>
      </section>
    </div>
  );
}

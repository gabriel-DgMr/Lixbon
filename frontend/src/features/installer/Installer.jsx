import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { LuLaptop, LuCopy, LuDownload, LuTerminal, LuFileCode } from 'react-icons/lu';

export default function Installer() {
  const [serverBaseUrl, setServerBaseUrl] = useState('');

  useEffect(() => {
    // Intentamos obtener el server_base_url del backend, o usamos el origen actual
    api.get('/api/dashboard/init')
      .then(res => {
        setServerBaseUrl(res.data.server_base_url);
      })
      .catch(() => {
        // Fallback: usar el origin del navegador sin /v1
        setServerBaseUrl(window.location.origin);
      });
  }, []);

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

  const base = serverBaseUrl || window.location.origin;
  const linuxCmd = `curl -fsSL ${base}/install.sh | bash`;
  const winCmd = `irm ${base}/install.ps1 | iex`;

  return (
    <div id="installer" className="section-content active">
      <section className="panel">
        <h2><LuLaptop style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Cliente CLI remoto</h2>
        <p className="muted">
          Instala la interfaz de terminal en otros equipos de la red para que chateen usando este servidor.
        </p>

        <div className="grid-2" style={{ marginTop: '1.5rem' }}>
          <div>
            <h3>Linux / macOS (bash)</h3>
            <div style={{ position: 'relative', marginTop: '0.5rem' }}>
              <pre><code id="cmd-linux-install">{linuxCmd}</code></pre>
              <button 
                className="copy-btn"
                onClick={() => handleCopy(linuxCmd)}
                style={{ 
                  position: 'absolute', 
                  top: '0.5rem', 
                  right: '0.5rem', 
                  background: 'rgba(255,255,255,0.1)', 
                  color: 'white',
                  cursor: 'pointer'
                }}
              >
                <LuCopy style={{ width: '16px' }} />
              </button>
            </div>
          </div>
          <div>
            <h3>Windows (PowerShell)</h3>
            <div style={{ position: 'relative', marginTop: '0.5rem' }}>
              <pre><code id="cmd-win-install">{winCmd}</code></pre>
              <button 
                className="copy-btn"
                onClick={() => handleCopy(winCmd)}
                style={{ 
                  position: 'absolute', 
                  top: '0.5rem', 
                  right: '0.5rem', 
                  background: 'rgba(255,255,255,0.1)', 
                  color: 'white',
                  cursor: 'pointer'
                }}
              >
                <LuCopy style={{ width: '16px' }} />
              </button>
            </div>
          </div>
        </div>

        <div
          style={{
            marginTop: '2rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1.5rem',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '8px',
            border: '1px solid var(--border)',
            flexWrap: 'wrap',
            gap: '1rem'
          }}
        >
          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>
              <LuDownload style={{ width: '18px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> 
              Descarga directa del script
            </h3>
            <p className="small muted" style={{ margin: 0 }}>
              Si prefieres no usar el instalador automático, puedes descargar el script Python directamente aquí.
            </p>
          </div>
          <a 
            href={`${base}/install/client_cli.py`} 
            download
            className="button"
            style={{
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'var(--primary)',
              color: 'white',
              padding: '0.75rem 1.25rem',
              borderRadius: '8px',
              fontWeight: '500',
              fontSize: '0.95rem'
            }}
          >
            <LuFileCode style={{ width: '16px' }} /> Descargar client_cli.py
          </a>
        </div>

        <div
          style={{
            marginTop: '2rem',
            padding: '1.5rem',
            background: 'var(--bg-color)',
            borderRadius: '8px',
            border: '1px dashed var(--border)'
          }}
        >
          <h3 style={{ marginBottom: '0.5rem' }}>
            <LuTerminal style={{ width: '18px', display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> 
            Uso después de instalar
          </h3>
          <p className="small muted" style={{ marginBottom: '1rem' }}>Abre una nueva terminal en el otro PC y ejecuta:</p>
          <code style={{ display: 'block', marginBottom: '0.5rem' }}>folax setup</code>
          <code style={{ display: 'block' }}>folax chat</code>
        </div>
      </section>
    </div>
  );
}

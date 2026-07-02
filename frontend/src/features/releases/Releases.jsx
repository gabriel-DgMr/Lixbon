import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { LuDownload, LuSparkles, LuCheck, LuCircleHelp, LuInfo } from 'react-icons/lu';

export default function Releases() {
  const [versions, setVersions] = useState([]);
  const [serverBaseUrl, setServerBaseUrl] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Obtener la URL del backend
    api.get('/api/dashboard/init')
      .then(res => {
        setServerBaseUrl(res.data.server_base_url || window.location.origin);
      })
      .catch(() => {
        setServerBaseUrl(window.location.origin);
      });

    // Obtener las versiones
    api.get('/api/versions')
      .then(res => {
        setVersions(res.data || []);
      })
      .catch(err => {
        console.error('Error cargando versiones:', err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const getAbsoluteDownloadUrl = (path) => {
    if (!path) return '#';
    if (path.startsWith('http')) return path;
    const base = (serverBaseUrl || window.location.origin).replace(/\/+$/, '');
    return `${base}${path}`;
  };

  return (
    <div id="releases-view" className="section-content active">
      <section className="panel">
        <div className="flex justify-between align-center" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2>
              <LuSparkles style={{ display: 'inline', verticalAlign: 'middle', marginRight: '8px', color: 'var(--primary)' }} /> 
              Versiones y Descargas de la App
            </h2>
            <p className="muted">
              Historial de lanzamientos de la App Folax Desktop y notas de cambios oficiales.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center align-center" style={{ padding: '3rem', color: 'var(--text-muted)' }}>
            Cargando versiones disponibles...
          </div>
        ) : versions.length === 0 ? (
          <div 
            className="flex flex-col align-center justify-center" 
            style={{ 
              padding: '4rem 2rem', 
              border: '1px dashed var(--border)', 
              borderRadius: '8px',
              textAlign: 'center',
              background: 'rgba(255,255,255,0.01)'
            }}
          >
            <LuInfo size={32} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
            <h3 style={{ color: '#fff', marginBottom: '0.5rem' }}>No hay versiones registradas aún</h3>
            <p className="muted small" style={{ maxWidth: '400px', margin: '0 auto 1.5rem' }}>
              El pipeline de CI/CD de GitHub Actions registrará y subirá los instaladores automáticamente aquí cuando compiles una versión.
            </p>
          </div>
        ) : (
          <div className="releases-list flex flex-col gap-6">
            {versions.map((v) => {
              const isStable = v.channel === 'stable';
              const downloadLink = getAbsoluteDownloadUrl(v.download_url);
              
              return (
                <div 
                  key={v.version} 
                  className="release-card"
                  style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border)',
                    borderRadius: '12px',
                    padding: '1.5rem',
                    transition: 'border-color 0.2s',
                  }}
                >
                  <div className="flex justify-between align-center" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '12px', marginBottom: '12px', flexWrap: 'wrap', gap: '1rem' }}>
                    <div className="flex align-center gap-2">
                      <h3 style={{ margin: 0, color: '#fff', fontSize: '1.25rem', fontFamily: 'JetBrains Mono' }}>
                        v{v.version}
                      </h3>
                      <span 
                        className="badge" 
                        style={{
                          fontSize: '0.75rem',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontWeight: '600',
                          background: isStable ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: isStable ? '#34d399' : '#fbbf24',
                          border: isStable ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(245, 158, 11, 0.3)'
                        }}
                      >
                        {v.channel.toUpperCase()}
                      </span>
                    </div>
                    <span className="muted font-mono small">{v.release_date}</span>
                  </div>

                  <h4 style={{ color: '#fff', marginTop: 0, marginBottom: '0.75rem', fontWeight: '500' }}>
                    {v.title}
                  </h4>

                  <ul style={{ paddingLeft: '1.25rem', margin: '0 0 1.5rem', color: 'var(--text-muted)' }}>
                    {v.changelog.map((change, idx) => (
                      <li key={idx} style={{ marginBottom: '0.4rem', fontSize: '0.9rem', lineHeight: '1.5' }}>
                        {change}
                      </li>
                    ))}
                  </ul>

                  <div className="flex justify-end">
                    <a 
                      href={downloadLink}
                      download={`app-folax-${v.version}-${v.channel}.msi`}
                      className="button"
                      style={{
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        background: 'var(--primary)',
                        color: 'white',
                        padding: '0.6rem 1.25rem',
                        borderRadius: '6px',
                        fontWeight: '500',
                        fontSize: '0.9rem',
                        boxShadow: '0 4px 12px rgba(88, 86, 214, 0.2)'
                      }}
                    >
                      <LuDownload style={{ width: '16px' }} /> Descargar Instalador
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <style dangerouslySetInnerHTML={{ __html: `
        .release-card:hover {
          border-color: var(--primary) !important;
        }
      `}} />
    </div>
  );
}

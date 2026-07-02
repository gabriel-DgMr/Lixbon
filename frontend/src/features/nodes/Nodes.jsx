import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { LuServer, LuRefreshCw, LuCircleCheck, LuCircleAlert, LuTriangleAlert, LuCpu, LuActivity } from 'react-icons/lu';

export default function Nodes() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [error, setError] = useState(null);

  const fetchNodes = async () => {
    try {
      const res = await api.get('/api/nodes');
      setNodes(res.data.nodos || []);
      setError(null);
    } catch (e) {
      console.error(e);
      setError('Error al obtener el estado de los nodos.');
    } finally {
      setLoading(false);
    }
  };

  const handleReloadConfig = async () => {
    setReloading(true);
    try {
      const res = await api.post('/api/nodes/reload');
      alert(`Configuración recargada. ${res.data.nodos} nodos cargados.`);
      fetchNodes();
    } catch (e) {
      alert('Error al recargar nodos');
    } finally {
      setReloading(false);
    }
  };

  useEffect(() => {
    fetchNodes();
    // Auto-refresh en tiempo real cada 5 segundos
    const interval = setInterval(fetchNodes, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="muted" style={{ padding: '2rem' }}>Cargando estado de los nodos...</div>;
  }

  return (
    <div id="nodes" className="section-content active">
      <section className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2><LuServer style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Active Nodes</h2>
            <p className="muted" style={{ margin: 0 }}>
              Monitoring compute resources across local cluster.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button 
              onClick={handleReloadConfig} 
              disabled={reloading}
              className="secondary"
              style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}
            >
              <LuRefreshCw style={{ width: '14px', marginRight: '4px', verticalAlign: 'middle' }} /> 
              {reloading ? 'Recargando...' : 'Recargar Nodos.json'}
            </button>
          </div>
        </div>

        {error && (
          <div className="error-box" style={{ marginBottom: '1.5rem' }}>
            <LuTriangleAlert />
            <span>{error}</span>
          </div>
        )}

        <div className="grid-2">
          {nodes && nodes.length > 0 ? (
            nodes.map((n, idx) => {
              const score = n.score ?? 0;
              const isCb = n.circuit_breaker ?? false;
              const isOnline = n.online ?? false;
              const modelos = n.modelos ?? [];

              return (
                <div key={idx} className="quick-card" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', position: 'relative' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-main)' }}>
                      {n.name || n.id || `Nodo ${idx + 1}`}
                    </h3>
                    <span>
                      {isOnline ? (
                        <span className="badge badge-ok" style={{ fontSize: '0.75rem' }}>
                          <LuCircleCheck style={{ width: '12px', marginRight: '4px', verticalAlign: 'middle' }} /> Online
                        </span>
                      ) : (
                        <span className="badge badge-error" style={{ fontSize: '0.75rem' }}>
                          <LuCircleAlert style={{ width: '12px', marginRight: '4px', verticalAlign: 'middle' }} /> Offline
                        </span>
                      )}
                    </span>
                  </div>

                  <p className="small muted" style={{ margin: 0 }}>
                    Dirección: <code>{n.ollama_url}</code>
                  </p>

                  <div className="stats-cards" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', marginTop: '0.5rem' }}>
                    <div className="stat-card" style={{ padding: '0.5rem', borderRadius: '6px' }}>
                      <span style={{ fontSize: '0.75rem', marginBottom: '0.2rem' }}>Puntuación</span>
                      <strong style={{ fontSize: '1.2rem' }}>{score}</strong>
                    </div>
                    <div className="stat-card" style={{ padding: '0.5rem', borderRadius: '6px' }}>
                      <span style={{ fontSize: '0.75rem', marginBottom: '0.2rem' }}>Circuit Breaker</span>
                      <strong style={{ fontSize: '1.2rem', color: isCb ? 'var(--error)' : 'var(--primary)' }}>
                        {isCb ? 'ACTIVO' : 'OK'}
                      </strong>
                    </div>
                  </div>

                  <div style={{ marginTop: '0.5rem' }}>
                    <span className="small font-medium" style={{ display: 'block', marginBottom: '0.25rem', color: 'var(--text-muted)' }}>
                      Modelos disponibles ({modelos.length}):
                    </span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                      {modelos.length > 0 ? (
                        modelos.map((m, mIdx) => (
                          <span 
                            key={mIdx} 
                            className="badge" 
                            style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-main)', border: '1px solid var(--border)', fontSize: '0.7rem', padding: '0.15rem 0.4rem' }}
                          >
                            {m.id}
                          </span>
                        ))
                      ) : (
                        <span className="small muted">Ninguno</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="muted text-center" style={{ gridColumn: 'span 2', padding: '2rem' }}>
              No hay nodos del cluster configurados o activos en nodes.json.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

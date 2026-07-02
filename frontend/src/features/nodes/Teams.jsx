import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { LuUsers } from 'react-icons/lu';

export default function Teams() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTeams = async () => {
    try {
      const res = await api.get('/api/dashboard/init');
      setData(res.data.clients || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTeams();
  }, []);

  if (loading) {
    return <div className="muted" style={{ padding: '2rem' }}>Cargando equipos...</div>;
  }

  return (
    <div id="clients" className="section-content active">
      <section className="panel">
        <h2><LuUsers style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} /> Equipos conectados</h2>
        <p className="muted" style={{ marginBottom: '1.5rem' }}>
          Métricas de uso segregadas por identificador de cliente (`client_id`).
        </p>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Identificador (client_id)</th>
                <th>Conversaciones</th>
                <th>Mensajes</th>
                <th>Tokens totales</th>
                <th>Última actividad</th>
              </tr>
            </thead>
            <tbody>
              {data && data.length > 0 ? (
                data.map((c, idx) => (
                  <tr key={idx}>
                    <td><strong>{c.client_id}</strong></td>
                    <td>{c.conversations}</td>
                    <td>{c.messages}</td>
                    <td><span style={{ color: 'var(--primary)', fontWeight: 600 }}>{c.total_tokens}</span></td>
                    <td className="small muted">{c.last_activity || '-'}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                    Aún no hay métricas de equipos.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

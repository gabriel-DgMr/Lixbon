import React, { useState, useEffect, useRef } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/ui/Sidebar';
import { LuMenu, LuBell, LuUser, LuLogOut, LuPlus, LuCircleAlert } from 'react-icons/lu';
import { useAuth } from '../features/auth/AuthContext';

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const notificationsRef = useRef(null);
  const profileRef = useRef(null);

  // Colapsar sidebar en móviles por defecto
  useEffect(() => {
    if (window.innerWidth <= 768) {
      setSidebarOpen(false);
    }
  }, []);

  // Cerrar dropdowns al hacer click afuera
  useEffect(() => {
    function handleClickOutside(event) {
      if (notificationsRef.current && !notificationsRef.current.contains(event.target)) {
        setNotificationsOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleConnectNodeClick = () => {
    alert("Para conectar un nuevo nodo, copia y ejecuta el instalador CLI de la pestaña 'Instalador CLI' en el otro PC.");
    navigate('/installer');
  };

  return (
    <div className="app-layout">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className={`main-content ${sidebarOpen ? '' : 'expanded'}`} id="main-content">
        <header className="top-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button 
              className="toggle-sidebar" 
              id="toggle-sidebar-btn" 
              title="Toggle menú"
              onClick={() => setSidebarOpen(prev => !prev)}
              style={{ cursor: 'pointer', background: 'transparent', border: 'none', color: '#fff' }}
            >
              <LuMenu size={20} />
            </button>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
              Cluster Status: <strong style={{ color: '#10b981' }}>ONLINE</strong>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', position: 'relative' }}>
            <button 
              onClick={handleConnectNodeClick}
              className="secondary" 
              style={{ 
                padding: '0.4rem 0.8rem', 
                fontSize: '0.8rem', 
                borderRadius: 'var(--radius)', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px',
                border: '1px solid var(--border-sidebar)'
              }}
            >
              <LuPlus size={14} /> Connect Node
            </button>

            {/* NOTIFICACIONES */}
            <div ref={notificationsRef} style={{ position: 'relative' }}>
              <button 
                onClick={() => { setNotificationsOpen(!notificationsOpen); setProfileOpen(false); }}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '6px' }}
                title="Notificaciones"
              >
                <div style={{ position: 'relative' }}>
                  <LuBell size={18} />
                  <span style={{ position: 'absolute', top: '-2px', right: '-2px', width: '6px', height: '6px', background: '#dc2626', borderRadius: '50%' }}></span>
                </div>
              </button>

              {notificationsOpen && (
                <div style={{
                  position: 'absolute',
                  right: 0,
                  top: '40px',
                  width: '320px',
                  background: '#18181b',
                  border: '1px solid var(--border-sidebar)',
                  borderRadius: 'var(--radius)',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 100,
                  padding: '0.75rem'
                }}>
                  <div style={{ borderBottom: '1px solid var(--border-sidebar)', paddingBottom: '0.5rem', marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '0.85rem', color: '#fff' }}>Notificaciones del sistema</strong>
                    <span style={{ fontSize: '0.7rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.1)', padding: '2px 6px', borderRadius: '4px' }}>3 nuevas</span>
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <li style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.5rem', fontSize: '0.8rem' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
                        <LuCircleAlert size={14} style={{ color: '#10b981', marginTop: '2px', shrink: 0 }} />
                        <div>
                          <p style={{ margin: 0, color: '#fafafa', fontWeight: 500 }}>Nodo C conectado</p>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Hace 5 minutos</span>
                        </div>
                      </div>
                    </li>
                    <li style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '0.5rem', fontSize: '0.8rem' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
                        <LuCircleAlert size={14} style={{ color: '#dc2626', marginTop: '2px', shrink: 0 }} />
                        <div>
                          <p style={{ margin: 0, color: '#fafafa', fontWeight: 500 }}>Fallo de conexión al modelo</p>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Hace 15 minutos</span>
                        </div>
                      </div>
                    </li>
                    <li style={{ fontSize: '0.8rem' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
                        <LuCircleAlert size={14} style={{ color: '#eab308', marginTop: '2px', shrink: 0 }} />
                        <div>
                          <p style={{ margin: 0, color: '#fafafa', fontWeight: 500 }}>API Key de durangogabriel... activa</p>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Hace 1 hora</span>
                        </div>
                      </div>
                    </li>
                  </ul>
                </div>
              )}
            </div>

            {/* PERFIL */}
            <div ref={profileRef} style={{ position: 'relative' }}>
              <button 
                onClick={() => { setProfileOpen(!profileOpen); setNotificationsOpen(false); }}
                style={{ 
                  background: '#27272a', 
                  border: '1px solid var(--border-sidebar)', 
                  color: '#fff', 
                  cursor: 'pointer', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '50%' 
                }}
                title="Mi Cuenta"
              >
                <LuUser size={16} />
              </button>

              {profileOpen && (
                <div style={{
                  position: 'absolute',
                  right: 0,
                  top: '40px',
                  width: '220px',
                  background: '#18181b',
                  border: '1px solid var(--border-sidebar)',
                  borderRadius: 'var(--radius)',
                  boxShadow: 'var(--shadow-lg)',
                  zIndex: 100,
                  padding: '0.75rem'
                }}>
                  <div style={{ borderBottom: '1px solid var(--border-sidebar)', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>
                    <p style={{ margin: 0, color: '#fafafa', fontWeight: 600, fontSize: '0.85rem' }}>{user?.username || 'Usuario'}</p>
                    <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.75rem' }}>{user?.email || 'admin@datacentgbx.online'}</p>
                  </div>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <li>
                      <button 
                        onClick={() => { setProfileOpen(false); navigate('/dashboard'); }}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', width: '100%', textAlign: 'left', padding: '4px 0', fontSize: '0.8rem', cursor: 'pointer' }}
                        onMouseOver={(e) => e.currentTarget.style.color = '#fff'}
                        onMouseOut={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                      >
                        Dashboard
                      </button>
                    </li>
                    <li>
                      <button 
                        onClick={() => { setProfileOpen(false); navigate('/keys'); }}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', width: '100%', textAlign: 'left', padding: '4px 0', fontSize: '0.8rem', cursor: 'pointer' }}
                        onMouseOver={(e) => e.currentTarget.style.color = '#fff'}
                        onMouseOut={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                      >
                        Mis Claves API
                      </button>
                    </li>
                    <li style={{ borderTop: '1px solid var(--border-sidebar)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
                      <button 
                        onClick={() => { setProfileOpen(false); logout(); }}
                        style={{ background: 'transparent', border: 'none', color: '#f87171', width: '100%', textAlign: 'left', padding: '4px 0', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <LuLogOut size={12} /> Cerrar sesión
                      </button>
                    </li>
                  </ul>
                </div>
              )}
            </div>
          </div>
        </header>
        <div className="container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

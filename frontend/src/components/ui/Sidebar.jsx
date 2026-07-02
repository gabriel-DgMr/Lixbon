import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LuLayoutDashboard, 
  LuServer, 
  LuCpu, 
  LuRouter, 
  LuTerminal, 
  LuSettings, 
  LuCircleHelp, 
  LuUsers,
  LuSparkles 
} from 'react-icons/lu';

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LuLayoutDashboard },
  { name: 'Active Nodes', href: '/nodes', icon: LuServer },
  { name: 'Interactive Chat', href: '/chat', icon: LuCpu },
  { name: 'AI Delegation', href: '/delegation', icon: LuRouter },
  { name: 'CLI Installer', href: '/installer', icon: LuTerminal },
  { name: 'App Releases', href: '/releases', icon: LuSparkles },
  { name: 'API Keys', href: '/keys', icon: LuSettings },
];

export function Sidebar({ isOpen, onClose }) {
  const handleNavLinkClick = () => {
    if (window.innerWidth <= 768) {
      onClose();
    }
  };

  return (
    <aside className={`sidebar ${isOpen ? 'open' : 'collapsed'}`} id="sidebar">
      {/* Brand / Logo */}
      <div className="brand">
        <div className="brand-info" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '4px',
            background: '#5856D6',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 'bold',
            fontSize: '1.1rem'
          }}>F</div>
          <div>
            <h1 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0, display: 'flex', flexDirection: 'column', gap: '2px', lineHeight: 1 }}>
              FOLAX DTC
            </h1>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0, fontFamily: 'JetBrains Mono', fontWeight: 500 }}>Local Cluster</p>
          </div>
        </div>
        <button className="close-sidebar" id="close-sidebar-btn" title="Cerrar menú" onClick={onClose}>
          <span>✕</span>
        </button>
      </div>

      {/* CTA Button: Deploy Model */}
      <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={() => window.location.href = '/delegation'}
          style={{
            width: '100%',
            background: 'var(--primary)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius)',
            padding: '0.6rem',
            fontWeight: 500,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            transition: 'background 0.2s'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'var(--primary-hover)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'var(--primary)'}
        >
          <LuSparkles size={14} /> Deploy Model
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="side-nav" id="main-nav">
        {navigation.map((item) => (
          <NavLink
            key={item.name}
            to={item.href}
            className={({ isActive }) => isActive ? 'active' : ''}
            onClick={handleNavLinkClick}
          >
            <item.icon className="h-5 w-5 shrink-0" />
            {item.name}
          </NavLink>
        ))}

        {/* Spacer to push footer links to the bottom */}
        <div style={{ flex: 1 }}></div>

        {/* Divider line */}
        <div style={{ borderTop: '1px solid var(--border)', margin: '0.5rem 0' }}></div>

        {/* Footer links mapping to Integrations (Docs) and Teams (Support) */}
        <NavLink
          to="/integrations"
          className={({ isActive }) => isActive ? 'active' : ''}
          onClick={handleNavLinkClick}
        >
          <LuCircleHelp className="h-5 w-5 shrink-0" />
          Docs
        </NavLink>
        <NavLink
          to="/teams"
          className={({ isActive }) => isActive ? 'active' : ''}
          onClick={handleNavLinkClick}
        >
          <LuUsers className="h-5 w-5 shrink-0" />
          Support
        </NavLink>
      </nav>
    </aside>
  );
}

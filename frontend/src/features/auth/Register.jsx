import React, { useState } from 'react';
import { useAuth } from './AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { LuTerminal, LuUser, LuLock, LuArrowRight } from 'react-icons/lu';
import './Auth.css';

export default function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (password !== passwordConfirm) {
      setError('Las contraseñas no coinciden');
      return;
    }

    setLoading(true);
    try {
      await register(username, password);
      setSuccess('Cuenta creada correctamente. ¡Bienvenido!');
      setTimeout(() => {
        navigate('/dashboard');
      }, 1200);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar usuario');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-wrapper">
        <div className="auth-card">
          <div className="auth-topbar">
            <div className="auth-topbar-icon">
              <LuTerminal size={16} />
            </div>
          </div>
          
          <div className="auth-card-body">
            <div className="auth-header">
              <h2>Crear Cuenta</h2>
              <p>Regístrate en LAN LLM Gateway</p>
            </div>
            
            {error && (
              <div className="error-box" style={{ fontSize: '0.85rem', padding: '0.75rem', marginBottom: '1rem', background: 'rgba(220, 38, 38, 0.1)', border: '1px solid rgba(220, 38, 38, 0.2)', color: '#f87171', borderRadius: '6px' }}>
                {error}
              </div>
            )}

            {success && (
              <div className="success-box" style={{ fontSize: '0.85rem', padding: '0.75rem', marginBottom: '1rem', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', color: '#34d399', borderRadius: '6px' }}>
                {success}
              </div>
            )}

            <div className="form-inner-box">
              <form id="registerForm" onSubmit={handleSubmit}>
                <div className="input-group">
                  <div className="input-header">
                    <label htmlFor="username">Usuario</label>
                  </div>
                  <div className="input-wrapper">
                    <LuUser className="input-icon" size={16} />
                    <input 
                      type="text" 
                      id="username"
                      value={username} 
                      onChange={e => setUsername(e.target.value)} 
                      required 
                      placeholder="nuevo_usuario" 
                      autoComplete="username" 
                    />
                  </div>
                </div>
                
                <div className="input-group">
                  <div className="input-header">
                    <label htmlFor="password">Contraseña</label>
                  </div>
                  <div className="input-wrapper">
                    <LuLock className="input-icon" size={16} />
                    <input 
                      type="password" 
                      id="password"
                      value={password} 
                      onChange={e => setPassword(e.target.value)} 
                      required 
                      placeholder="Mínimo 6 caracteres" 
                      minLength={6} 
                      autoComplete="new-password" 
                    />
                  </div>
                </div>

                <div className="input-group">
                  <div className="input-header">
                    <label htmlFor="password2">Confirmar contraseña</label>
                  </div>
                  <div className="input-wrapper">
                    <LuLock className="input-icon" size={16} />
                    <input 
                      type="password" 
                      id="password2"
                      value={passwordConfirm} 
                      onChange={e => setPasswordConfirm(e.target.value)} 
                      required 
                      placeholder="Repite tu contraseña" 
                      minLength={6} 
                      autoComplete="new-password" 
                    />
                  </div>
                </div>
                
                <button type="submit" className="submit-btn" disabled={loading}>
                  {loading ? 'Procesando...' : 'Registrarse'} <LuArrowRight size={16} />
                </button>
              </form>
            </div>
            
            <div className="auth-links" style={{ marginTop: '1.5rem', textAlignment: 'center' }}>
              ¿Ya tienes cuenta? <Link to="/login" style={{ color: '#6366f1', fontWeight: 600 }}>Inicia sesión</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

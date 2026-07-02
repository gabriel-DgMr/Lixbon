import React, { useState } from 'react';
import { useAppStore } from './store/appStore';
import { useTheme } from './hooks/useTheme';
import { useConnection } from './hooks/useConnection';
import { useVersion } from './hooks/useVersion';

// Layout Components
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { Onboarding } from './components/Onboarding';
import { UpdateBanner } from './components/UpdateBanner';

// Section Pages
import { Auth } from './sections/Auth/Auth';
import { Workspace } from './sections/Workspace/Workspace';
import { Terminal } from './sections/Terminal/Terminal';
import { Metrics } from './sections/Metrics/Metrics';
import { Services } from './sections/Services/Services';
import { Commands } from './sections/Commands/Commands';
import { Settings } from './sections/Settings/Settings';

export default function App() {
  // Inicializar hooks de ciclo de vida
  useTheme();
  useConnection();
  const { 
    updateInfo, 
    installUpdate, 
    isDownloading, 
    downloadProgress 
  } = useVersion();

  const { serverUrl, activeSection, apiKey } = useAppStore();
  const [activeTab, setActiveTab] = useState('cluster'); // Usado por Terminal (Cluster | Logs | Metrics)

  // Si no se ha configurado la URL del túnel, obligar Onboarding
  if (!serverUrl) {
    return <Onboarding />;
  }

  // Si no hay API Key de sesión activa, obligar Login
  if (!apiKey) {
    return <Auth />;
  }

  // Renderizado dinámico de la sección seleccionada
  const renderSection = () => {
    switch (activeSection) {
      case 'terminal':
        return <Terminal activeTab={activeTab} />;
      case 'workspace':
        return <Workspace />;
      case 'metrics':
        return <Metrics />;
      case 'services':
        return <Services />;
      case 'commands':
        return <Commands />;
      case 'settings':
        return <Settings />;
      default:
        return <Terminal activeTab={activeTab} />;
    }
  };

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <TopBar activeTab={activeTab} setActiveTab={setActiveTab} />
        
        <UpdateBanner 
          updateInfo={updateInfo}
          onInstall={installUpdate}
          isDownloading={isDownloading}
          downloadProgress={downloadProgress}
        />
        
        <div className="section-container">
          {renderSection()}
        </div>
      </div>
    </div>
  );
}

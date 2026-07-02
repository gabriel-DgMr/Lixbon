import { useState, useEffect } from 'react';
import { useAppStore } from '../store/appStore';
import { api } from '../lib/api';
// Importación dinámica de Tauri para evitar errores fuera de Tauri (por ejemplo, en navegador)
let tauriUpdater = null;
import('@tauri-apps/plugin-updater')
  .then(m => {
    tauriUpdater = m;
  })
  .catch(err => {
    console.warn('Tauri updater plugin not loaded:', err);
  });

export function useVersion() {
  const { serverUrl, connectionStatus } = useAppStore();
  const [currentVersion, setCurrentVersion] = useState('2.4.0');
  const [updateInfo, setUpdateInfo] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);

  const checkForUpdates = async () => {
    if (!serverUrl || connectionStatus !== 'connected') return;

    try {
      // 1. Preguntar al servidor local la versión instalada (o usar la estática de Rust)
      const current = '2.4.0';
      setCurrentVersion(current);

      // 2. Comprobar contra el endpoint del servidor si hay actualización
      const res = await api.get(`/api/updates/check?v=${current}`);
      if (res && res.update_available) {
        setUpdateInfo(res);
      } else {
        setUpdateInfo(null);
      }
    } catch (e) {
      console.error('[updater] Error al verificar actualizaciones:', e);
    }
  };

  const installUpdate = async () => {
    if (!tauriUpdater) {
      alert('Tauri updater plugin not loaded or not running inside desktop container.');
      return;
    }

    try {
      setIsDownloading(true);
      const update = await tauriUpdater.check();
      if (update) {
        let downloaded = 0;
        let contentLength = 0;
        
        await update.downloadAndInstall((event) => {
          switch (event.event) {
            case 'Started':
              contentLength = event.data.contentLength || 0;
              break;
            case 'Progress':
              downloaded += event.data.chunkLength;
              if (contentLength > 0) {
                setDownloadProgress(Math.round((downloaded / contentLength) * 100));
              }
              break;
            case 'Finished':
              setIsDownloading(false);
              break;
          }
        });
      }
    } catch (error) {
      console.error('[updater] Error instalando actualización:', error);
      setIsDownloading(false);
      alert('Error en la descarga: ' + error.message);
    }
  };

  useEffect(() => {
    checkForUpdates();
    const interval = setInterval(checkForUpdates, 30 * 60 * 1000); // Cada 30 minutos
    return () => clearInterval(interval);
  }, [serverUrl, connectionStatus]);

  return {
    currentVersion,
    updateInfo,
    isDownloading,
    downloadProgress,
    checkForUpdates,
    installUpdate
  };
}

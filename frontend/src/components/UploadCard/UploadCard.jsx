import React from 'react';
import './UploadCard.css';

export default function UploadCard({ file, setFile, handleUpload, status, rowsProcessed, rowsErrors, processingStatus, downloadUrl, onDownload, isProcessing }) {
  return (
    <div className="app-container fade-in stagger-3">
      <div className="upload-box">
        <div className="actions">
          <div className="select-row">
            <label className="file-wrapper">
              <input
                type="file"
                onChange={(e) => setFile(e.target.files[0])}
                className="file-input"
                accept=".xlsx,.xls"
                disabled={isProcessing}
              />
              <span className="file-button">Seleccionar archivo</span>
              <span className="file-name">{file ? file.name : 'Ningún archivo seleccionado'}</span>
            </label>
            <p className="file-hint">Tamaño máximo 5 MB. Solo archivos Excel (.xlsx, .xls).</p>
          </div>

          <div className="process-row">
            <button onClick={handleUpload} className="primary-btn" disabled={isProcessing} aria-busy={isProcessing}>
              {isProcessing ? 'Procesando...' : 'Procesar'}
            </button>
          </div>
        </div>

        <div className="actions" style={{ marginTop: 6 }}>
          {downloadUrl ? (
            <button className="download-btn" onClick={onDownload} title="Descargar resultado" aria-label="Descargar resultado">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                <path d="M12 3v12" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M8 11l4 4 4-4" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M21 21H3" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          ) : null}
        </div>
      </div>
      {rowsProcessed !== null && (
        <p className="processed-count fade-in stagger-5">Filas procesadas con éxito: {rowsProcessed}</p>
      )}

      {rowsErrors !== null && rowsErrors > 0 && (
        <p className="processed-error fade-in stagger-6">Errores: {rowsErrors} — revisa la columna `resultado` en el archivo de salida.</p>
      )}

      {processingStatus && processingStatus !== 'completed' && (
        <p className="processed-status fade-in stagger-6">Estado: {processingStatus}</p>
      )}
    </div>
  );
}

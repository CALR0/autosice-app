import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import "./App.css";
import Header from "./components/Header";
import FAQ from "./components/FAQ";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import UploadCard from "./components/UploadCard";
import ExampleTable from "./components/ExampleTable";

function Home({file, setFile, handleUpload, status, rowsProcessed, rowsErrors, processingStatus, downloadUrl, onDownload, isProcessing}){
  return (
    <>
      <Hero />

      <UploadCard
        file={file}
        setFile={setFile}
        handleUpload={handleUpload}
        status={status}
        rowsProcessed={rowsProcessed}
        rowsErrors={rowsErrors}
        processingStatus={processingStatus}
        downloadUrl={downloadUrl}
        onDownload={onDownload}
        isProcessing={isProcessing}
      />

      <ExampleTable />
    </>
  );
}

function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");
  const [rowsProcessed, setRowsProcessed] = useState(null);
  const [rowsErrors, setRowsErrors] = useState(null);
  const [processingStatus, setProcessingStatus] = useState(null);
  const [currentRow, setCurrentRow] = useState(null);
  const [totalRows, setTotalRows] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState('resultado.xlsx');
  const [isProcessing, setIsProcessing] = useState(false);
  const API_URL = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5000';
  const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

  // Resume polling if a job was enqueued previously
  useEffect(() => {
    const jid = localStorage.getItem('autosice_job_id');
    if (jid) {
      pollJob(jid);
      setIsProcessing(true);
      setStatus('Reanudando procesamiento...');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll a job by id and update UI state. Keeps polling until finished/error.
  const pollJob = async (job_id) => {
    const statusUrl = `${API_URL}/job/${job_id}/status`;
    const downloadEndpoint = `${API_URL}/job/${job_id}/download`;

    const tick = async () => {
      try {
        const s = await fetch(statusUrl);
        if (!s.ok) throw new Error('Status fetch failed');
        const meta = await s.json();

        setRowsProcessed(meta.rows_processed ?? null);
        setRowsErrors(meta.rows_errors ?? null);
        setTotalRows(meta.total_rows ?? null);

        if (meta.status === 'queued' || meta.status === 'running') {
          const current = (meta.rows_processed || 0) + 1;
          setCurrentRow(current);
          setProcessingStatus(null);
          if (meta.total_rows) setStatus(`Procesando fila ${current} de ${meta.total_rows}`);
          else setStatus(`Procesando fila ${current}`);
          setTimeout(tick, 2000);
          return;
        }

        if (meta.status === 'finished') {
          setStatus('Archivo listo — pulsa Descargar');
          setDownloadUrl(downloadEndpoint);
          setIsProcessing(false);
          setProcessingStatus(null);
          setCurrentRow(null);
          localStorage.removeItem('autosice_job_id');
          return;
        }

        if (meta.status === 'error') {
          setStatus('Error: ' + (meta.error || 'Procesamiento falló'));
          setIsProcessing(false);
          setProcessingStatus(null);
          setCurrentRow(null);
          localStorage.removeItem('autosice_job_id');
          return;
        }
      } catch (err) {
        setStatus('Error consultando estado: ' + (err.message || err));
        setIsProcessing(false);
        localStorage.removeItem('autosice_job_id');
      }
    };

    tick();
  };

  const handleUpload = async () => {
    if (!file) {
      setStatus("Selecciona un archivo primero");
      return;
    }

    // Client-side validation: extension and size
    const name = (file.name || '').toLowerCase();
    if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
      setStatus('Solo se permiten archivos Excel (.xlsx, .xls)');
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setStatus('Archivo demasiado grande (máx 5 MB).');
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setStatus("Encolando y procesando...");
    setIsProcessing(true);

    try {
      // Use async enqueue so we can show per-row progress
      const response = await fetch(`${API_URL}/enqueue`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errText = await response.text().catch(() => null);
        throw new Error(errText || "Error en el servidor");
      }

      const data = await response.json();
      const job_id = data.job_id;
      // persist job id so page reloads can resume polling
      try { localStorage.setItem('autosice_job_id', job_id); } catch (e) {}

      const statusUrl = `${API_URL}${data.status_url}`;
      const downloadEndpoint = `${API_URL}${data.download_url}`;

      // Poll status until finished/error
      const poll = async () => {
        try {
          const s = await fetch(statusUrl);
          if (!s.ok) throw new Error('Status fetch failed');
          const meta = await s.json();

          setRowsProcessed(meta.rows_processed ?? null);
          setRowsErrors(meta.rows_errors ?? null);
          setTotalRows(meta.total_rows ?? null);
          // update current row (1-based) while running
          if (meta.status === 'queued' || meta.status === 'running') {
            const current = (meta.rows_processed || 0) + 1;
            setCurrentRow(current);
            setProcessingStatus(null);
          } else {
            setCurrentRow(null);
            setProcessingStatus(null);
          }

          if (meta.status === 'queued' || meta.status === 'running') {
            const current = (meta.rows_processed || 0) + 1;
            if (meta.total_rows) {
              setStatus(`Procesando fila ${current} de ${meta.total_rows}`);
            } else {
              setStatus(`Procesando fila ${current}`);
            }
            setTimeout(poll, 2000);
            return;
          }

          if (meta.status === 'finished') {
            setStatus('Archivo listo — pulsa Descargar');
            setDownloadUrl(downloadEndpoint);
            setIsProcessing(false);
            setProcessingStatus(null);
            setCurrentRow(null);
            return;
          }

          if (meta.status === 'error') {
            setStatus('Error: ' + (meta.error || 'Procesamiento falló'));
            setIsProcessing(false);
            setProcessingStatus(null);
            setCurrentRow(null);
            return;
          }
        } catch (err) {
          setStatus('Error consultando estado: ' + (err.message || err));
          setIsProcessing(false);
        }
      };

      // start polling via central function so reload/resume works
      pollJob(job_id);

    } catch (error) {
      setStatus("Error: " + error.message);
      setIsProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = downloadName || 'resultado.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    // keep the URL so user can choose location again; revoke happens when a new file is created
  };

  return (
    <BrowserRouter>
      <div className="app-body">
        <Header />
        <TitleUpdater />
        <div className="page-inner">
          <Routes>
            <Route path="/" element={<Home file={file} setFile={setFile} handleUpload={handleUpload} status={status} rowsProcessed={rowsProcessed} rowsErrors={rowsErrors} processingStatus={processingStatus} downloadUrl={downloadUrl} onDownload={handleDownload} isProcessing={isProcessing} currentRow={currentRow} totalRows={totalRows} />} />
            <Route path="/faq" element={<FAQ />} />
            {/* future routes can be added here */}
          </Routes>
        </div>
        {/* footer */}
        <Footer />
      </div>
    </BrowserRouter>
  );
}

function TitleUpdater(){
  const location = useLocation();
  useEffect(() => {
    const path = location.pathname;
    if (path === '/' || path === '') {
      document.title = 'Inicio';
    } else if (path === '/faq') {
      document.title = 'FAQ';
    } else {
      document.title = 'SICE-TAC';
    }
  }, [location]);
  return null;
}

export default App;
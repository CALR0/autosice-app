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
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadName, setDownloadName] = useState('resultado.xlsx');
  const [isProcessing, setIsProcessing] = useState(false);
  const API_URL = import.meta.env.VITE_BACKEND_URL || 'http://127.0.0.1:5000';
  const MAX_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

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

    setStatus("Procesando... esto puede tardar");
    setIsProcessing(true);

    try {
      const response = await fetch(`${API_URL}/procesar`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Error en el servidor");
      }

      // Try to read an optional header with number of processed rows
      const headerRows = response.headers.get('X-Rows-Processed');
      const headerErrors = response.headers.get('X-Rows-Errors');
      const headerStatus = response.headers.get('X-Processing-Status');

      setRowsProcessed(headerRows ? Number(headerRows) : null);
      setRowsErrors(headerErrors ? Number(headerErrors) : null);
      setProcessingStatus(headerStatus || null);

      const blob = await response.blob();

      // create object URL and store it so user must click download
      if (downloadUrl) {
        try { window.URL.revokeObjectURL(downloadUrl); } catch(e){}
      }
      const url = window.URL.createObjectURL(blob);
      setDownloadUrl(url);

      // try to read filename from headers
      const cd = response.headers.get('Content-Disposition');
      if (cd) {
        const match = /filename\*=UTF-8''([^;\n]+)/i.exec(cd) || /filename="?([^";\n]+)"?/i.exec(cd);
        if (match) setDownloadName(decodeURIComponent(match[1]));
      }

      setStatus("Archivo listo — pulsa Descargar");
    } catch (error) {
      setStatus("Error: " + error.message);
    } finally {
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
            <Route path="/" element={<Home file={file} setFile={setFile} handleUpload={handleUpload} status={status} rowsProcessed={rowsProcessed} rowsErrors={rowsErrors} processingStatus={processingStatus} downloadUrl={downloadUrl} onDownload={handleDownload} isProcessing={isProcessing} />} />
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
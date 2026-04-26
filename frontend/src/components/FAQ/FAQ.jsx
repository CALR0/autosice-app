import React, { useState } from 'react';
import './FAQ.css';

const FAQ_ITEMS = [
  {
    q: '¿Para qué sirve esta app?',
    a: (
      <>
        <p>Permite cargar un archivo Excel con filas que representan vehículos/transportes y calcula automáticamente los costos operativos consultando SICE-TAC mediante automatización. Devuelve un archivo de salida con una columna <strong>resultado</strong> que indica el estado por fila.</p>
      </>
    ),
  },
  {
    q: 'Formato del Excel',
    a: (
      <>
        <p>La primera fila debe contener los encabezados exactamente como se muestran en el ejemplo. Columnas requeridas (nombres exactos, sin comas): <span className="headers-inline"><strong>configuracion, condicion, carroceria, tipo_carga, origen, destino, hora_cargue, hora_descargue</strong></span></p>
        <p>Las celdas deben contener valores reconocibles por SICE-TAC. Si un valor no existe, la fila se marcará con un error explícito en la columna <em>resultado</em> (ej.: "No existe condicion: LLENO").</p>
      </>
    ),
  },
  {
    q: 'Qué esperar después de procesar',
    a: (
      <>
        <ul className="no-bullets">
          <li>Un archivo <code>resultado.xlsx</code> descargable.</li>
          <li>Información: <code>Filas procesadas con éxito</code>, <code>Filas con errores</code>, <code>Estado del proceso</code>.</li>
        </ul>
      </>
    ),
  },
  {
    q: 'Comportamiento en caso de fallos',
    a: (
      <>
        <p>La aplicacion web reintenta por fila cuando hay fallos de comunicación (hasta ~40s). Errores de datos no detienen el procesamiento de otras filas y quedan registrados en la salida.</p>
      </>
    ),
  },
  {
    q: 'Limitaciones y recomendaciones',
    a: (
      <>
        <ul className="no-bullets">
          <li>No se persiste el archivo <code>input.xlsx</code> en el servidor; se usa almacenamiento temporal.</li>
          <li>Si hay muchos errores, revisa que los valores coincidan exactamente con los válidos.</li>
          <li>Archivos grandes tardan más dependiendo del sitio remoto.</li>
        </ul>
      </>
    ),
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null);

  const toggle = (i) => setOpenIndex(openIndex === i ? null : i);

  return (
    <section className="faq-section page-content">
      <h2 className="faq-title fade-in stagger-2">Preguntas frecuentes</h2>

      <div className="faq-list">
        {FAQ_ITEMS.map((it, i) => (
          <div key={i} className={`faq-item ${openIndex === i ? 'open' : ''} fade-in stagger-${(i % 6) + 1}`}>
            <button className="faq-question fade-in stagger-3" onClick={() => toggle(i)} aria-expanded={openIndex === i}>
              <span className="question-text">{it.q}</span>
              <span className="chevron" aria-hidden>▸</span>
            </button>
            <div className="faq-answer" style={{ maxHeight: openIndex === i ? '800px' : '0px' }}>
              <div className={`faq-answer-inner fade-in-slow stagger-${((i+2) % 6) + 1}`}>
                {it.a}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

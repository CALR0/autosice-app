import React from 'react';
import './ExampleTable.css';

export default function ExampleTable() {
  return (
    <section className="example-section fade-in stagger-5" aria-labelledby="example-title">
      <h2 id="example-title" className="fade-in stagger-5">FORMATO EXCEL</h2>
      <p className="example-desc fade-in stagger-6">La primera fila debe contener los encabezados tal como se muestran. Cada fila siguiente representa un vehículo / transporte, a continuación un ejemplo:</p>

      <div className="table-wrap">
        <div className="table-card">
          <div className="table-inner">
            <table className="sample-table" role="table">
          <thead>
            <tr>
              <th>configuracion</th>
              <th>condicion</th>
              <th>carroceria</th>
              <th>tipo_carga</th>
              <th>origen</th>
              <th>destino</th>
              <th>hora_cargue</th>
              <th>hora_descargue</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>3S2</td>
              <td>CARGADO</td>
              <td>ESTACAS</td>
              <td>GENERAL</td>
              <td>BOGOTÁ</td>
              <td>MEDELLIN</td>
              <td>2</td>
              <td>2</td>
            </tr>
            <tr>
              <td>2S2</td>
              <td>VACIO</td>
              <td>FURGON</td>
              <td>NO APLICA</td>
              <td>BARRANQUILLA</td>
              <td>CALI</td>
              <td>2</td>
              <td>2</td>
            </tr>
          </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

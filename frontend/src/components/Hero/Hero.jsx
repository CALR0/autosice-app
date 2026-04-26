import React from 'react';
import './Hero.css';

export default function Hero() {
  return (
    <header className="hero fade-in stagger-1">
      <h1 className="app-title fade-in stagger-1">
        <span className="autosice">AUTOSICE</span><span className="accent">SICE-TAC</span>
      </h1>
      <p className="app-desc hero-desc fade-in stagger-2">
        Carga un archivo Excel con múltiples vehículos y calcula automáticamente
        los costos operativos usando SICE-TAC.
      </p>
    </header>
  );
}

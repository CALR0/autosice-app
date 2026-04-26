import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import './Header.css';

export default function Header() {
  const location = useLocation();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => {
      setScrolled(window.scrollY > 20);
    };
    handler();
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);
  return (
    <header className={`site-header ${scrolled ? 'scrolled' : ''}`}>
      <nav className="header-nav">
        <Link to="/" className={`nav-link nav-home ${location.pathname === '/' ? 'active' : ''}`}>INICIO</Link>
        <Link to="/faq" className={`nav-link nav-faq ${location.pathname === '/faq' ? 'active' : ''}`}>FAQ</Link>
        <a className="nav-link nav-sicetac" href="https://plc.mintransporte.gov.co/runtime/empresa/ctl/sicetac/mid/417" target="_blank" rel="noopener noreferrer">SICE-TAC</a>
      </nav>
    </header>
  );
}

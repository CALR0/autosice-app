import React, { useEffect, useState } from 'react';
import './Footer.css';

export default function Footer(){
  const year = 2026;
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const check = () => {
      const scrollTop = window.scrollY || window.pageYOffset;
      const docHeight = document.documentElement.scrollHeight;
      const winHeight = window.innerHeight;
      const nearBottom = (scrollTop + winHeight) >= (docHeight - 40);
      setVisible(nearBottom);
    };

    check();
    window.addEventListener('scroll', check, { passive: true });
    window.addEventListener('resize', check);
    return () => {
      window.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
  }, []);

  return (
    <footer className={`site-footer ${visible ? 'visible' : ''}`}>
      <div className="footer-inner">
        <span className="copyright">Todos los derechos reservados © {year}</span>
      </div>
    </footer>
  );
}

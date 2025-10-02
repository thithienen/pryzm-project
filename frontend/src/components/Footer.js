import React from 'react';
import HealthStatus from './HealthStatus';
import './Footer.css';

const Footer = () => {
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-left">
          <div className="attribution">
            <span className="attribution-text">
              Source code: <a href="https://github.com/thithienen/pryzm-project" target="_blank" rel="noopener noreferrer">@https://github.com/thithienen/pryzm-project</a>
            </span>
          </div>
        </div>
        <div className="footer-right">
          <HealthStatus />
        </div>
      </div>
    </footer>
  );
};

export default Footer;

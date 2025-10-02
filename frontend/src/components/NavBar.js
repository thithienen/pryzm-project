import React from 'react';
import './NavBar.css';

function NavBar({ activeTab, onTabChange }) {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <div className="navbar-brand">
          <span className="brand-text">Pryzm Project</span>
        </div>
        <div className="navbar-tabs">
          <button
            className={`navbar-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => onTabChange('chat')}
          >
            <span className="tab-icon">💬</span>
            <span className="tab-text">Chat</span>
          </button>
          <button
            className={`navbar-tab ${activeTab === 'readme' ? 'active' : ''}`}
            onClick={() => onTabChange('readme')}
          >
            <span className="tab-icon">📖</span>
            <span className="tab-text">README</span>
          </button>
        </div>
      </div>
    </nav>
  );
}

export default NavBar;

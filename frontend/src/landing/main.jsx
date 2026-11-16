import React from 'react';
import { createRoot } from 'react-dom/client';
import LandingPage from './LandingPage.jsx';
import './landing.css';

createRoot(document.getElementById('landing-root')).render(
  <React.StrictMode><LandingPage /></React.StrictMode>
);

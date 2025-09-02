/**
 * This file will automatically be loaded by vite and run in the "renderer" context.
 * To learn more about the differences between the "main" and the "renderer" context in
 * Electron, visit:
 *
 * https://electronjs.org/docs/tutorial/process-model
 *
 * By default, Node.js integration in this file is disabled. When enabling Node.js integration
 * in a renderer process, please be aware of potential security implications. You can read
 * more about security risks here:
 *
 * https://electronjs.org/docs/tutorial/security
 */

import './index.css';

console.log('🚀 Braster Empire Trading Bot Dashboard loaded');

// Dashboard state
interface DashboardState {
  isRunning: boolean;
  trades: number;
  pnl: number;
}

const state: DashboardState = {
  isRunning: false,
  trades: 0,
  pnl: 0
};

// DOM elements
const startBtn = document.getElementById('start-bot') as HTMLButtonElement;
const stopBtn = document.getElementById('stop-bot') as HTMLButtonElement;
const viewLogsBtn = document.getElementById('view-logs') as HTMLButtonElement;
const statusDot = document.querySelector('.status-dot') as HTMLElement;
const statusText = statusDot?.nextElementSibling as HTMLElement;

// Update UI based on state
function updateUI() {
  if (state.isRunning) {
    statusDot?.classList.remove('offline');
    statusDot?.classList.add('online');
    if (statusText) statusText.textContent = 'Online';
    
    startBtn.disabled = true;
    stopBtn.disabled = false;
  } else {
    statusDot?.classList.remove('online');
    statusDot?.classList.add('offline');
    if (statusText) statusText.textContent = 'Offline';
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
  
  // Update stats
  const statValue = document.querySelector('.stat-value') as HTMLElement;
  const tradesValue = document.querySelectorAll('.stat-value')[1] as HTMLElement;
  
  if (statValue) {
    statValue.textContent = `$${state.pnl.toFixed(2)}`;
    statValue.style.color = state.pnl >= 0 ? '#10b981' : '#ef4444';
  }
  
  if (tradesValue) {
    tradesValue.textContent = state.trades.toString();
  }
}

// Event handlers
startBtn?.addEventListener('click', () => {
  console.log('Starting trading bot...');
  state.isRunning = true;
  updateUI();
  
  // Simulate some trading activity
  const interval = setInterval(() => {
    if (!state.isRunning) {
      clearInterval(interval);
      return;
    }
    
    // Simulate a trade
    if (Math.random() > 0.7) {
      state.trades++;
      state.pnl += (Math.random() - 0.5) * 20; // Random P&L between -10 and +10
      updateUI();
    }
  }, 3000);
});

stopBtn?.addEventListener('click', () => {
  console.log('Stopping trading bot...');
  state.isRunning = false;
  updateUI();
});

viewLogsBtn?.addEventListener('click', () => {
  console.log('Opening logs window...');
  // This could open a new window or modal with logs
  alert('Logs functionality would open a detailed view of bot activity and trades.');
});

// Initialize UI
updateUI();

// Add some visual feedback
document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.card');
  cards.forEach((card, index) => {
    setTimeout(() => {
      card.classList.add('animate-in');
    }, index * 100);
  });
});

// Add some CSS for the animation
const style = document.createElement('style');
style.textContent = `
  .card {
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.5s ease, transform 0.5s ease;
  }
  
  .card.animate-in {
    opacity: 1;
    transform: translateY(0);
  }
`;
document.head.appendChild(style);

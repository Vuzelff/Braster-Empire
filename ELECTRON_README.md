# Braster Empire - Electron Desktop Application

A modern desktop application built with **Electron Forge**, **Vite**, and **TypeScript** for monitoring and controlling the Braster Empire Futures Trading Bot.

## 🚀 Features

- **Modern Tech Stack**: Built with Electron Forge, Vite, and TypeScript
- **Trading Dashboard**: Real-time monitoring of bot status and performance
- **Interactive Controls**: Start/stop bot, view configuration, and access logs
- **Responsive Design**: Clean, modern interface with dark theme
- **Cross-Platform**: Runs on Windows, macOS, and Linux
- **Security**: Context isolation and secure preload scripts

## 📦 Quick Start

### Prerequisites
- Node.js 18+ 
- npm or yarn

### Installation & Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server**:
   ```bash
   npm start
   ```

3. **Run linting**:
   ```bash
   npm run lint
   ```

4. **Package application**:
   ```bash
   npm run package
   ```

5. **Build distributables**:
   ```bash
   npm run make
   ```

## 🏗️ Project Structure

```
├── src/
│   ├── main.ts          # Electron main process
│   ├── preload.ts       # Preload script for secure IPC
│   ├── renderer.ts      # Renderer process (UI logic)
│   └── index.css        # Application styles
├── index.html           # Main HTML template
├── forge.config.ts      # Electron Forge configuration
├── vite.*.config.ts     # Vite configurations
├── tsconfig.json        # TypeScript configuration
└── package.json         # Project dependencies and scripts
```

## ⚙️ Configuration

### Electron Forge
The application uses Electron Forge with the Vite plugin for:
- Fast development server with HMR
- TypeScript compilation
- Cross-platform packaging
- Security hardening with Fuses

### Vite Integration
Three separate Vite configurations:
- `vite.main.config.ts` - Main process bundling
- `vite.preload.config.ts` - Preload script bundling  
- `vite.renderer.config.ts` - Renderer process bundling

## 🛠️ Development

### Available Scripts

- `npm start` - Start development server
- `npm run package` - Package app for current platform
- `npm run make` - Create platform-specific distributables
- `npm run publish` - Publish to configured targets
- `npm run lint` - Run ESLint

### Hot Module Replacement
Vite provides fast HMR during development. Changes to renderer code will update instantly without restart.

### Debugging
In development mode, DevTools are automatically opened for debugging the renderer process.

## 📱 Features Overview

### Dashboard Components

1. **Bot Status Indicator**
   - Real-time online/offline status
   - Visual status indicator with pulse animation

2. **Active Trading Pairs**
   - Display currently configured trading pairs
   - Color-coded tags for easy identification

3. **Configuration Display**
   - Timeframe, leverage, and position size settings
   - Read-only view of current bot configuration

4. **Performance Metrics**
   - Real-time P&L tracking
   - Trade count and statistics

5. **Control Panel**
   - Start/Stop bot functionality
   - Access to logs and detailed views

### Security Features

- **Context Isolation**: Renderer process runs in isolated context
- **Preload Scripts**: Secure IPC communication between processes
- **Content Security**: Prevention of unsafe content execution
- **Window Security**: Controlled window creation and navigation

## 🔧 Customization

### Styling
The app uses a modern dark theme with CSS custom properties. Modify `src/index.css` to customize:
- Color scheme
- Layout and spacing
- Component styling
- Responsive breakpoints

### Functionality
Extend the app by modifying:
- `src/renderer.ts` - UI logic and interactions
- `src/main.ts` - Main process functionality
- `src/preload.ts` - Secure IPC communications

### Build Configuration
Customize the build process via:
- `forge.config.ts` - Electron Forge settings
- `vite.*.config.ts` - Vite build configurations
- `package.json` - Dependencies and scripts

## 📋 Production Build

### Packaging
Create a packaged version for your platform:
```bash
npm run package
```

### Distribution
Create platform-specific installers:
```bash
npm run make
```

Supported formats:
- **Windows**: Squirrel installer
- **macOS**: ZIP archive
- **Linux**: DEB and RPM packages

## 🤝 Integration with Trading Bot

This Electron app serves as a desktop interface for the Python trading bot (`bot.py`). Future enhancements could include:

- **IPC Communication**: Direct communication with the Python bot process
- **Real-time Data**: Live trading data and performance metrics
- **Configuration Management**: GUI-based bot configuration
- **Log Streaming**: Real-time log viewing and filtering
- **Trade History**: Detailed trade history and analytics

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Troubleshooting

### Common Issues

1. **Build Failures**: Ensure Node.js 18+ and clean `node_modules`
2. **TypeScript Errors**: Check `tsconfig.json` configuration
3. **Vite Issues**: Verify Vite configuration files
4. **Packaging Problems**: Check Electron Forge configuration

### Getting Help

- Check the [Electron Forge documentation](https://www.electronforge.io/)
- Review [Vite documentation](https://vitejs.dev/)
- TypeScript issues: [TypeScript Handbook](https://www.typescriptlang.org/docs/)
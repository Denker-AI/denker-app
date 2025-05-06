# Denker Frontend

This is the frontend application for Denker, an AI-powered desktop assistant built with React, TypeScript, and Electron.

## Features

- Modern UI with Material UI components
- Desktop application for macOS and Windows
- Real-time communication with backend using WebSockets
- Authentication with Auth0
- State management with Zustand
- File upload and management
- Conversation history

## Prerequisites

- Node.js 16+
- npm or yarn
- Backend API running (see backend README)

## Getting Started

1. Clone the repository
2. Install dependencies:

```bash
cd denker-app/frontend
npm install
```

3. Create a `.env` file based on `.env.example` and fill in your Auth0 credentials and API URLs.

4. Start the development server:

```bash
npm run electron:dev
```

This will start both the Vite development server and Electron.

## Project Structure

```
denker-app/frontend/
├── public/             # Static assets and Electron main process files
├── src/
│   ├── components/     # React components
│   │   ├── MainWindow/ # Components for the main window
│   │   └── SubWindow/  # Components for the sub window
│   ├── hooks/          # Custom React hooks
│   ├── pages/          # Page components
│   ├── services/       # API and WebSocket services
│   ├── store/          # Zustand stores
│   ├── utils/          # Utility functions
│   ├── App.tsx         # Main App component
│   ├── main.tsx        # Entry point
│   └── theme.ts        # Material UI theme
├── .env.example        # Example environment variables
├── package.json        # Dependencies and scripts
├── tsconfig.json       # TypeScript configuration
└── vite.config.ts      # Vite configuration
```

## Building for Production

To build the application for production:

```bash
npm run electron:build
```

This will create distributable packages in the `dist` directory.

## Development

### Adding a New Component

1. Create a new file in the appropriate directory under `src/components/`
2. Import and use the component in the relevant page or parent component

### Adding a New Page

1. Create a new file in `src/pages/`
2. Add a route in `src/App.tsx`

### Adding a New API Endpoint

1. Add the endpoint to the API service in `src/services/api.ts`
2. Use the endpoint in the relevant hook or component

## License

MIT 
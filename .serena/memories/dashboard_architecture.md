# BugRewind Dashboard Architecture

## Overview
The BugRewind dashboard is a React/Vite single-page application that provides real-time monitoring and visualization of deployment workflows. It communicates with the FastAPI backend via WebSocket for live updates and REST API for initial data.

## Frontend Stack
- **Framework**: React 18.2.0 with Vite 4.4.5
- **UI Components**: Custom components with lucide-react icons
- **Markdown Rendering**: react-markdown with remark-gfm for GitHub Flavored Markdown
- **Styling**: CSS modules with index.css for global styles

## Project Structure
```
bugrewind/dashboard/
├── index.html          # Entry HTML file
├── vite.config.js      # Vite configuration
├── package.json        # Dependencies and scripts
├── src/
│   ├── main.jsx       # React entry point
│   ├── App.jsx        # Main application component
│   ├── index.css      # Global styles
│   └── WatcherMetrics.jsx # Watcher monitoring component
```

## Key Components

### App.jsx
- Main application component
- Manages WebSocket connection to backend
- Handles real-time state updates
- Renders deployment workflow status
- Displays markdown summaries from agents

### WatcherMetrics.jsx
- Displays monitoring data from RewindWatcher
- Shows container health status
- Visualizes crash statistics and diagnostics

### WebSocket Integration
- Connection to `ws://localhost:8000/ws`
- Receives real-time updates on workflow progress
- Updates UI components without page refresh

## Backend Integration
- **FastAPI Server**: Runs on port 8000
- **WebSocket Endpoint**: `/ws` for real-time communication
- **REST Endpoints**: 
  - `GET /api/state` - Get current workflow state
  - `POST /api/trigger` - Trigger new deployment workflow
  - `GET /api/watcher/metrics` - Get watcher monitoring data

## Development Commands
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Key Features
1. **Real-time Workflow Visualization**: See agent progress as it happens
2. **Markdown Summary Display**: Render agent outputs with proper formatting
3. **Watcher Monitoring**: View container health and crash diagnostics
4. **Responsive Design**: Works on desktop and mobile
5. **Error Handling**: Graceful error states and loading indicators

## Integration Points
- Connects to `bugrewind/dashboard_api.py` FastAPI backend
- Uses `bugrewind/utils/llm.py` for LLM communication
- Shares database with `bugrewind/utils/db.py` for watcher data
- WebSocket events mirror `BugRewindState` updates from the workflow graph

## Styling Guidelines
- Use CSS modules for component-specific styles
- Global styles in `index.css` for typography and colors
- Lucide-react icons for consistent iconography
- Responsive breakpoints: mobile (< 768px), tablet (768px-1024px), desktop (>1024px)

## State Management
- React hooks (useState, useEffect) for local state
- WebSocket context for real-time updates
- No external state management library (Redux, Zustand) required

## Error Handling
- Network error boundaries for API failures
- WebSocket reconnection logic
- Loading states for async operations
- User-friendly error messages
import React, { useState, useEffect, useRef } from 'react';
import { Coffee, Shield, Code, Container, FileText, CheckCircle, Activity, AlertCircle, Terminal } from 'lucide-react';

const AGENT_NODES = [
  { id: 'orchestrator', label: 'Orchestrator', icon: Coffee },
  { id: 'critic', label: 'Critic', icon: Shield },
  { id: 'coder', label: 'Coder', icon: Code },
  { id: 'docker_gen', label: 'Docker Gen', icon: Container },
  { id: 'validation', label: 'Validation', icon: Activity },
  { id: 'solomon', label: 'Solomon', icon: CheckCircle },
  { id: 'summary', label: 'Summary', icon: FileText },
];

function App() {
  const [repoPath, setRepoPath] = useState('');
  const [prompt, setPrompt] = useState('Deploy this project securely via Docker.');
  const [activeNode, setActiveNode] = useState(null);
  const [logs, setLogs] = useState([]);
  const [state, setState] = useState({
    issues: [],
    patches: [],
    dockerfile: '',
    summary: '',
  });
  const [isRunning, setIsRunning] = useState(false);

  const logEndRef = useRef(null);
  const ws = useRef(null);

  useEffect(() => {
    // Setup WebSocket
    ws.current = new WebSocket('ws://localhost:8000/ws');

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'node_update') {
        setActiveNode(data.node);
        setState(prev => ({ ...prev, ...data.updates }));

        // Add pseudo-log if logs are mixed in or just node transition
        addLog(`Transitioned to [${data.node}]`);
      } else if (data.type === 'workflow_complete') {
        setIsRunning(false);
        setActiveNode(null);
        addLog('🏁 Workflow completed successfully.');
      } else if (data.type === 'error') {
        setIsRunning(false);
        addLog(`❌ Error: ${data.message}`);
      }
    };

    return () => ws.current.close();
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { time, message: msg }]);
  };

  const startWorkflow = async () => {
    setIsRunning(true);
    setLogs([]);
    setLogs([{ time: new Date().toLocaleTimeString(), message: '🚀 Invoking BugRewind workflow...' }]);

    try {
      const res = await fetch('http://localhost:8000/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath, deploy_prompt: prompt }),
      });
      const data = await res.json();
      addLog(data.message);
    } catch (err) {
      addLog('Failed to connect to API server.');
      setIsRunning(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Coffee size={32} color="#967259" />
          <h1 style={{ fontWeight: 800, fontSize: '1.5rem', letterSpacing: '-0.02em' }}>BugRewind Dashboard</h1>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <input
            className="input-field"
            placeholder="Repo Path (Absolute)"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
          />
          <button
            className="btn-primary"
            onClick={startWorkflow}
            disabled={isRunning || !repoPath}
          >
            {isRunning ? 'Running...' : 'Deploy Now'}
          </button>
        </div>
      </header>

      <div className="dashboard-grid">
        {/* Agent Flow Graph */}
        <div className="panel graph-container">
          <div className="panel-title"><Activity size={14} /> Agent Execution Flow</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', justifyContent: 'center', height: '100%', alignItems: 'center' }}>
            {AGENT_NODES.map((node, i) => (
              <React.Fragment key={node.id}>
                <div className={`node ${activeNode === node.id ? 'active' : ''}`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <node.icon size={18} />
                    <span style={{ fontWeight: 600 }}>{node.label}</span>
                  </div>
                </div>
                {i < AGENT_NODES.length - 1 && (
                  <div style={{ height: '20px', width: '2px', background: 'var(--color-border)' }}></div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Live Logs */}
        <div className="panel logs-container">
          <div className="panel-title"><Terminal size={14} /> Real-time Logs</div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {logs.map((log, i) => (
              <div key={i} className="log-entry">
                <span className="log-time">[{log.time}]</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>

        {/* Inspection Panel */}
        <div className="panel preview-container">
          <div className="panel-title"><FileText size={14} /> Deployment Artifacts</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto' }}>
            {state.issues?.length > 0 && (
              <div style={{ padding: '8px', background: '#3c3633', borderRadius: '4px' }}>
                <div style={{ color: '#dbc1ac', fontSize: '0.8rem', fontWeight: 700, marginBottom: '4px' }}>ISSUES FOUND: {state.issues.length}</div>
                {state.issues.map((iss, i) => <div key={i} style={{ fontSize: '0.8rem', opacity: 0.8 }}>• {iss.title || iss.description}</div>)}
              </div>
            )}
            {state.dockerfile && (
              <div style={{ padding: '8px', background: '#3c3633', borderRadius: '4px' }}>
                <div style={{ color: '#dbc1ac', fontSize: '0.8rem', fontWeight: 700, marginBottom: '4px' }}>DOCKERFILE PREVIEW</div>
                <pre style={{ fontSize: '0.75rem', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>{state.dockerfile}</pre>
              </div>
            )}
            {state.summary && (
              <div style={{ padding: '12px', background: '#4a423f', borderRadius: '4px', border: '1px solid var(--color-accent)' }}>
                <div style={{ fontWeight: 700, marginBottom: '8px' }}>FINAL REPORT</div>
                <div style={{ fontSize: '0.85rem' }}>{state.summary}</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

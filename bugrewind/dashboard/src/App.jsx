import React, { useState, useEffect, useRef } from 'react';
import { Coffee, Shield, Code, Container, FileText, CheckCircle, Activity, Terminal, Cpu, Info, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
    plan: '',
    file_manifest: {},
    iteration: 0,
    max_iterations: 3,
    docker_build_log: '',
    docker_run_log: '',
    docker_status: ''
  });
  const [isRunning, setIsRunning] = useState(false);
  const [showInfoModal, setShowInfoModal] = useState(false);

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
    setState({
      issues: [], patches: [], dockerfile: '', summary: '',
      plan: '', file_manifest: {}, iteration: 0, max_iterations: 3,
      docker_build_log: '', docker_run_log: '', docker_status: ''
    });

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

  const activeIndex = AGENT_NODES.findIndex(n => n.id === activeNode);
  const manifestCount = Object.keys(state.file_manifest || {}).length;

  return (
    <div className="app-container">
      <header>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Coffee size={36} color="#dbc1ac" style={{ filter: 'drop-shadow(0 0 15px rgba(219, 193, 172, 0.4))' }} />
          <h1 style={{ fontWeight: 800, fontSize: '1.75rem', letterSpacing: '-0.02em', margin: 0, background: 'linear-gradient(135deg, #ece0d1, #967259)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>BugRewind</h1>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flex: 1, maxWidth: '600px', marginLeft: '40px' }}>
          <button 
            style={{ background: 'transparent', border: 'none', color: '#dbc1ac', cursor: 'pointer', padding: '8px', borderRadius: '50%', display: 'flex', transition: 'transform 0.2s' }}
            onClick={() => setShowInfoModal(true)}
            onMouseOver={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
            onMouseOut={(e) => e.currentTarget.style.transform = 'scale(1)'}
            title="Connection Info"
          >
            <Info size={24} />
          </button>
          <input
            className="input-field"
            placeholder="Repository Path (Absolute)"
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
          <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><Activity size={16} /> Agent Execution Flow</span>
            {state.iteration > 0 && <span style={{ fontSize: '0.75rem', opacity: 0.8, color: '#dbc1ac' }}>Iteration: {state.iteration} / {state.max_iterations}</span>}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0', justifyContent: 'flex-start', height: '100%', alignItems: 'center', overflowY: 'auto', padding: '10px 0' }}>
            {AGENT_NODES.map((node, i) => {
              const isActive = activeNode === node.id;
              const isConnectorActive = isRunning && (i <= activeIndex || activeIndex === -1);
              
              return (
                <React.Fragment key={node.id}>
                  <div className={`node ${isActive ? 'active' : ''}`}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center' }}>
                      <node.icon size={20} color={isActive ? '#dbc1ac' : 'currentColor'} />
                      <span style={{ fontWeight: isActive ? 700 : 500, letterSpacing: '0.05em' }}>{node.label}</span>
                    </div>
                  </div>
                  {i < AGENT_NODES.length - 1 && (
                    <div className={`node-connector ${isConnectorActive ? 'active' : ''}`}></div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Live Logs */}
        <div className="panel logs-container">
          <div className="panel-title"><Terminal size={16} /> Real-time Logs</div>
          <div style={{ overflowY: 'auto', flex: 1, paddingRight: '10px' }}>
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
          <div className="panel-title"><FileText size={16} /> Deployment Artifacts</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto', paddingRight: '10px' }}>
            
            {/* 1. File Manifest */}
            {manifestCount > 0 && (
              <div style={{ padding: '16px', background: 'rgba(255,255,255, 0.03)', borderRadius: '12px', border: '1px solid var(--color-border)' }}>
                <div style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em' }}>FILES IN CONTEXT: {manifestCount}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {Object.keys(state.file_manifest).map(f => (
                    <span key={f} style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--color-border)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.75rem', fontFamily: 'monospace' }}>{f}</span>
                  ))}
                </div>
              </div>
            )}

            {/* 2. Orchestrator Plan */}
            {state.plan && (
              <div style={{ padding: '16px', background: 'rgba(219, 193, 172, 0.05)', borderRadius: '12px', border: '1px solid rgba(219, 193, 172, 0.2)' }}>
                <div style={{ color: '#dbc1ac', fontSize: '0.85rem', fontWeight: 800, marginBottom: '8px', letterSpacing: '0.05em' }}>ORCHESTRATOR PLAN</div>
                <div className="markdown-body" style={{ fontSize: '0.85rem', lineHeight: 1.5, opacity: 0.9 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.plan}</ReactMarkdown>
                </div>
              </div>
            )}

            {/* 3. Issues */}
            {state.issues?.length > 0 && (
              <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '12px' }}>
                <div style={{ color: '#f87171', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em' }}>ISSUES FOUND: {state.issues.length}</div>
                {state.issues.map((iss, i) => (
                  <div key={i} className="card-item" style={{ borderLeft: '3px solid #ef4444' }}>
                    <span className="issue-dot">●</span> 
                    {iss.title || iss.description}
                  </div>
                ))}
              </div>
            )}

            {/* 4. Patches */}
            {state.patches?.length > 0 && (
              <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.08)', borderRadius: '12px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <div style={{ color: '#10b981', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em' }}>PATCHES APPLIED: {state.patches.length}</div>
                {state.patches.map((p, i) => (
                  <div key={i} className="card-item" style={{ borderLeft: '3px solid #10b981', overflowX: 'auto' }}>
                    <div style={{ fontWeight: 'bold', fontSize: '0.8rem', marginBottom: '8px', color: '#10b981' }}>📝 {p.file}</div>
                    <pre style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: '#ece0d1', margin: 0 }}>
{p.description || "Modified file configuration."}
                    </pre>
                  </div>
                ))}
              </div>
            )}

            {/* Dockerfile Preview */}
            {state.dockerfile && (
              <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <div style={{ color: '#dbc1ac', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em' }}>DOCKERFILE PREVIEW</div>
                <pre style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', fontFamily: "'JetBrains Mono', monospace", color: '#ece0d1' }}>{state.dockerfile}</pre>
              </div>
            )}

            {/* 5. Docker Logs */}
            {(state.docker_build_log || state.docker_run_log) && (
              <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '12px', border: '1px solid var(--color-border)' }}>
                <div style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em', display: 'flex', justifyContent: 'space-between' }}>
                  <span>DOCKER OUTPUT</span>
                  {state.docker_status && <span style={{ color: state.docker_status.includes('fail') ? '#f87171' : '#10b981' }}>{state.docker_status}</span>}
                </div>
                
                {state.docker_build_log && (
                  <details style={{ marginBottom: '8px' }}>
                    <summary style={{ cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-accent)' }}>Build Log</summary>
                    <pre style={{ marginTop: '8px', padding: '12px', background: 'rgba(0,0,0,0.4)', borderRadius: '6px', fontSize: '0.7rem', maxHeight: '150px', overflowY: 'auto', fontFamily: 'monospace', color: '#ece0d1', whiteSpace: 'pre-wrap' }}>
                      {state.docker_build_log}
                    </pre>
                  </details>
                )}
                
                {state.docker_run_log && (
                  <details>
                    <summary style={{ cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-accent)' }}>Run Log</summary>
                    <pre style={{ marginTop: '8px', padding: '12px', background: 'rgba(0,0,0,0.4)', borderRadius: '6px', fontSize: '0.7rem', maxHeight: '150px', overflowY: 'auto', fontFamily: 'monospace', color: '#ece0d1', whiteSpace: 'pre-wrap' }}>
                      {state.docker_run_log}
                    </pre>
                  </details>
                )}
              </div>
            )}

            {/* Final Summary */}
            {state.summary && (
              <div style={{ padding: '20px', background: 'rgba(219, 193, 172, 0.05)', borderRadius: '12px', border: '1px solid rgba(219, 193, 172, 0.3)', animation: 'slide-in 0.5s ease' }}>
                <div style={{ fontWeight: 800, marginBottom: '12px', color: '#dbc1ac', fontSize: '1.1rem' }}>FINAL REPORT</div>
                <div className="markdown-body" style={{ fontSize: '0.9rem', lineHeight: '1.6' }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{state.summary}</ReactMarkdown>
                </div>
              </div>
            )}
            
            {/* Empty State */}
            {(!manifestCount && !state.plan && !state.issues?.length && !state.dockerfile && !state.summary) && (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', opacity: 0.3, flexDirection: 'column', gap: '10px' }}>
                <Activity size={48} />
                <p>Awaiting workflow artifacts...</p>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Connection Info Modal */}
      {showInfoModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }}>
          <div className="panel" style={{ width: '600px', maxWidth: '90%', padding: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0, color: '#dbc1ac', display: 'flex', alignItems: 'center', gap: '12px', fontSize: '1.5rem', fontWeight: 800 }}><Info size={28} /> Integration Guide</h2>
              <button 
                onClick={() => setShowInfoModal(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', display: 'flex' }}
              >
                <X size={28} />
              </button>
            </div>
            
            <h3 style={{ fontSize: '1.1rem', color: '#ece0d1', marginBottom: '12px' }}>Terminal CLI</h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--color-text-dim)', marginBottom: '8px' }}>Execute the workflow instantly on any folder straight from your shell:</p>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border)', marginBottom: '28px', fontFamily: 'monospace', fontSize: '0.85rem' }}>
              python -m bugrewind.main &lt;path_to_repo&gt;
            </div>
            
            <h3 style={{ fontSize: '1.1rem', color: '#ece0d1', marginBottom: '12px' }}>MCP Server</h3>
            <p style={{ fontSize: '0.9rem', color: 'var(--color-text-dim)', marginBottom: '12px', lineHeight: 1.5 }}>
              BugRewind has a built-in FastMCP interface. To let tools like Claude or Cursor invoke the LangGraph pipeline for you, add this strictly to your config file:
            </p>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '8px', border: '1px solid var(--color-border)', fontFamily: 'monospace', fontSize: '0.85rem' }}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#dbc1ac' }}>
{`"bugrewind": {
  "command": "uv",
  "args": ["run", "-m", "bugrewind.mcp_server"]
}`}
              </pre>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;

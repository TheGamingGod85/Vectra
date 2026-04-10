import React, { useState, useEffect } from 'react';
import { Activity, Server, AlertCircle, CheckCircle, RefreshCw, Archive, Info, Eye, X, Terminal, Lightbulb } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function WatcherMetrics() {
  const [data, setData] = useState({ containers: [], metrics: {} });
  const [loading, setLoading] = useState(true);
  const [inspectContainer, setInspectContainer] = useState(null);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/watcher/containers');
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error("Failed to fetch watcher metrics", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'monitoring': return '#10b981'; // Green
      case 'analyzing': return '#f59e0b'; // Amber
      case 'notified': return '#3b82f6'; // Blue
      case 'lost': return '#ef4444'; // Red
      default: return 'var(--color-text-dim)';
    }
  };

  const { metrics, containers } = data;

  return (
    <div className="watcher-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px', height: '100%' }}>
      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' }}>
        <MetricCard icon={<Server />} label="Total Deployments" value={metrics.totalDeployments || 0} color="var(--color-accent)" />
        <MetricCard icon={<Activity />} label="Active Monitoring" value={metrics.activeMonitoring || 0} color="#10b981" />
        <MetricCard icon={<AlertCircle />} label="Incidents Analyzed" value={metrics.incidentsAnalyzed || 0} color="#f59e0b" />
        <MetricCard icon={<Archive />} label="Containers Lost" value={metrics.containersLost || 0} color="#ef4444" />
      </div>

      {/* Main Table */}
      <div className="panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="panel-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span><Activity size={16} style={{ marginRight: '8px' }}/> Monitored Containers</span>
          <button 
            onClick={fetchMetrics} 
            style={{ background: 'none', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? "spinning" : ""} /> Refresh
          </button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, paddingRight: '4px' }}>
          {containers.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', opacity: 0.5, flexDirection: 'column', gap: '10px' }}>
              <Info size={32} />
              <p>No containers currently tracked by RewindWatcher.</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', textAlign: 'left', color: 'var(--color-text-dim)' }}>
                  <th style={{ padding: '12px 8px' }}>Container ID</th>
                  <th style={{ padding: '12px 8px' }}>Repository</th>
                  <th style={{ padding: '12px 8px' }}>Deployed At</th>
                  <th style={{ padding: '12px 8px' }}>Target Email</th>
                  <th style={{ padding: '12px 8px' }}>Status</th>
                  <th style={{ padding: '12px 8px', textAlign: 'center' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {containers.map((c) => (
                  <tr key={c.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.2s' }} onMouseOver={(e) => e.currentTarget.style.background='rgba(255,255,255,0.02)'} onMouseOut={(e) => e.currentTarget.style.background='transparent'}>
                    <td style={{ padding: '12px 8px', fontFamily: 'monospace', color: 'var(--color-accent)' }}>{c.container_id.substring(0, 12)}</td>
                    <td style={{ padding: '12px 8px' }}>{c.repository_path.split(/[\/\\]/).pop()}</td>
                    <td style={{ padding: '12px 8px', color: 'var(--color-text-dim)' }}>{new Date(c.deployed_at).toLocaleString()}</td>
                    <td style={{ padding: '12px 8px' }}>{c.target_email}</td>
                    <td style={{ padding: '12px 8px' }}>
                      <span style={{ 
                        padding: '4px 8px', 
                        borderRadius: '12px', 
                        background: `${getStatusColor(c.status)}20`, 
                        color: getStatusColor(c.status),
                        fontWeight: 'bold',
                        fontSize: '0.75rem',
                        textTransform: 'uppercase'
                      }}>
                        {c.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 8px', textAlign: 'center' }}>
                      <button 
                        onClick={() => setInspectContainer(c)}
                        style={{ background: 'transparent', border: '1px solid var(--color-border)', borderRadius: '6px', color: 'var(--color-text)', padding: '6px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', transition: 'all 0.2s' }}
                        title="Inspect Container"
                        onMouseOver={(e) => { e.currentTarget.style.borderColor = 'var(--color-accent)'; e.currentTarget.style.color = 'var(--color-accent)'; }}
                        onMouseOut={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.color = 'var(--color-text)'; }}
                      >
                        <Eye size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Inspect Modal */}
      {inspectContainer && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999
        }}>
          <div className="panel" style={{ width: '600px', maxWidth: '90%', padding: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0, color: '#dbc1ac', display: 'flex', alignItems: 'center', gap: '12px', fontSize: '1.5rem', fontWeight: 800 }}>
                <Eye size={28} /> Inspect Container
              </h2>
              <button 
                onClick={() => setInspectContainer(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--color-text-dim)', cursor: 'pointer', display: 'flex' }}
              >
                <X size={28} />
              </button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '70vh', overflowY: 'auto', paddingRight: '8px' }}>
              <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Container ID</div>
                <div style={{ fontFamily: 'monospace', fontSize: '1rem', color: 'var(--color-accent)' }}>{inspectContainer.container_id}</div>
              </div>
              
              <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Repository Path</div>
                <div style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>{inspectContainer.repository_path}</div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Deployed At</div>
                  <div style={{ fontSize: '0.9rem' }}>{new Date(inspectContainer.deployed_at).toLocaleString()}</div>
                </div>

                <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Status</div>
                  <div style={{ fontSize: '0.9rem', color: getStatusColor(inspectContainer.status), fontWeight: 'bold', textTransform: 'uppercase' }}>
                    {inspectContainer.status}
                  </div>
                </div>
              </div>

              <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.2)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>Target Email</div>
                <div style={{ fontSize: '0.9rem' }}>{inspectContainer.target_email}</div>
              </div>

              {/* Conversation / Diagnostic Data */}
              {(inspectContainer.diagnostic_report || inspectContainer.fix_recommendation) && (
                <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <h3 style={{ color: 'var(--color-accent)', margin: '8px 0 0', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.2rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '8px' }}>
                    <Activity size={20} /> AI Forensics Analysis
                  </h3>

                  {inspectContainer.diagnostic_report && (
                    <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px' }}>
                      <div style={{ color: '#f87171', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Terminal size={16} /> DIAGNOSTIC REPORT
                      </div>
                      <div className="markdown-body" style={{ fontSize: '0.85rem' }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{inspectContainer.diagnostic_report}</ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {inspectContainer.fix_recommendation && (
                    <div style={{ padding: '16px', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: '8px' }}>
                      <div style={{ color: '#10b981', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Lightbulb size={16} /> FIX RECOMMENDATION
                      </div>
                      <div className="markdown-body" style={{ fontSize: '0.85rem' }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{inspectContainer.fix_recommendation}</ReactMarkdown>
                      </div>
                    </div>
                  )}

                  {inspectContainer.container_logs && (
                    <div style={{ padding: '16px', background: 'rgba(0, 0, 0, 0.4)', border: '1px solid var(--color-border)', borderRadius: '8px' }}>
                      <div style={{ color: 'var(--color-text-dim)', fontSize: '0.85rem', fontWeight: 800, marginBottom: '12px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        Raw Container Logs
                      </div>
                      <pre style={{ margin: 0, padding: '12px', background: 'rgba(0,0,0,0.5)', borderRadius: '6px', fontSize: '0.75rem', maxHeight: '200px', overflowY: 'auto', fontFamily: 'monospace', color: '#ece0d1', whiteSpace: 'pre-wrap' }}>
                        {inspectContainer.container_logs}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style>{`
        .spinning { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

function MetricCard({ icon, label, value, color }) {
  return (
    <div className="panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
      <div style={{ background: `${color}15`, padding: '12px', borderRadius: '12px', color: color, display: 'flex' }}>
        {React.cloneElement(icon, { size: 24 })}
      </div>
      <div>
        <div style={{ color: 'var(--color-text-dim)', fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>{label}</div>
        <div style={{ color: 'var(--color-text)', fontSize: '1.75rem', fontWeight: 800 }}>{value}</div>
      </div>
    </div>
  );
}

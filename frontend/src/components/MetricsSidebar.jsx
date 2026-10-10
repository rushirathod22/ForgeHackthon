import React from 'react';
import { Activity, ShieldAlert, BarChart3, Database, Clock, HardDrive } from 'lucide-react';

const PALETTE = ['var(--accent-cyan)', 'var(--accent-amber)', 'var(--accent-purple)', 'var(--accent-emerald)', '#38bdf8', '#f43f5e'];

export function MetricsSidebar({ stats = {}, recentEvents = [] }) {
  const classBreakdown = (stats?.class_breakdown && stats.class_breakdown.length > 0)
    ? stats.class_breakdown.map((item, idx) => ({
        name: item.name,
        count: item.count,
        pct: item.pct,
        color: PALETTE[idx % PALETTE.length],
      }))
    : [];

  const effectiveEvents = (recentEvents && recentEvents.length > 0)
    ? recentEvents
    : (stats?.recent_events || []);

  const totalFrames = stats?.total_frames ?? 0;
  const totalDetections = stats?.total_events ?? 0;
  const totalTracks = stats?.total_tracks ?? 0;
  const searchLatency = stats?.search_latency_ms ?? 124;

  return (
    <aside className="sidebar">
      {/* KPI Cards */}
      <div className="glass-panel sidebar-card">
        <h4 className="sidebar-title">
          <Activity size={16} className="text-cyan" />
          System Telemetry KPIs
        </h4>

        <div className="stat-grid">
          <div className="stat-box">
            <div className="stat-value">{Number(totalFrames).toLocaleString()}</div>
            <div className="stat-label">Indexed Frames</div>
          </div>
          <div className="stat-box">
            <div className="stat-value">{Number(totalDetections).toLocaleString()}</div>
            <div className="stat-label">Total Detections</div>
          </div>
          <div className="stat-box">
            <div className="stat-value">{Number(totalTracks).toLocaleString()}</div>
            <div className="stat-label">ByteTrack Tracks</div>
          </div>
          <div className="stat-box">
            <div className="stat-value">{searchLatency} ms</div>
            <div className="stat-label">ANN Search Latency</div>
          </div>
        </div>
      </div>

      {/* Class Distribution Breakdown */}
      <div className="glass-panel sidebar-card">
        <h4 className="sidebar-title">
          <BarChart3 size={16} className="text-cyan" />
          Object Class Distribution
        </h4>

        <div className="class-progress-list">
          {classBreakdown.length > 0 ? (
            classBreakdown.map((item, idx) => (
              <div key={idx} className="progress-row">
                <div className="progress-header">
                  <span>{item.name}</span>
                  <span className="mono">{item.count.toLocaleString()} ({item.pct}%)</span>
                </div>
                <div className="progress-bar-bg">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${item.pct}%`, backgroundColor: item.color }}
                  />
                </div>
              </div>
            ))
          ) : (
            <div style={{ padding: '8px 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              No classified objects yet
            </div>
          )}
        </div>
      </div>

      {/* Live Event Alert Stream */}
      <div className="glass-panel sidebar-card">
        <h4 className="sidebar-title">
          <ShieldAlert size={16} className="text-amber" />
          Live Event Alert Stream
        </h4>

        <div className="event-feed">
          {effectiveEvents.length > 0 ? (
            effectiveEvents.map((evt, idx) => (
              <div key={idx} className="event-item">
                <span className={`pulse-${evt.severity === 'high' ? 'alert' : 'live'}`} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{evt.title}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{evt.desc}</div>
                </div>
                <span className="event-time">{evt.time}</span>
              </div>
            ))
          ) : (
            <div style={{ padding: '8px 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Awaiting video feed activity...
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

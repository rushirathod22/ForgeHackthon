import React from 'react';
import { Camera, ShieldCheck, Cpu, Database, FileCheck, Activity } from 'lucide-react';

export function Navbar({ onOpenExportModal, stats = null }) {
  const frameDisplay = stats?.total_frames !== undefined
    ? `${Number(stats.total_frames).toLocaleString()} Frames`
    : 'Index Ready';
  const trackDisplay = stats?.total_tracks !== undefined
    ? `${Number(stats.total_tracks).toLocaleString()} Tracks`
    : 'Tracking Active';

  return (
    <header className="navbar">
      <div className="brand-section">
        <div className="brand-icon">
          <Camera size={22} />
        </div>
        <div>
          <div className="brand-title">RetailVisionGuard</div>
          <div className="brand-subtitle">AI-Powered Natural Language Video Intelligence Platform</div>
        </div>
      </div>

      <div className="status-pills">
        <div className="status-item">
          <span className="pulse-live"></span>
          <Cpu size={14} className="text-muted" />
          <span>YOLO11 Engine</span>
          <span className="badge badge-emerald">Ready</span>
        </div>

        <div className="status-item">
          <Database size={14} className="text-muted" />
          <span>FAISS Vector Index</span>
          <span className="badge badge-cyan">{frameDisplay}</span>
        </div>

        <div className="status-item">
          <Activity size={14} className="text-muted" />
          <span>ByteTrack Tracker</span>
          <span className="badge badge-purple">{trackDisplay}</span>
        </div>

        <button 
          className="search-btn" 
          onClick={onOpenExportModal}
          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
        >
          <FileCheck size={14} />
          Export Evidence
        </button>
      </div>
    </header>
  );
}

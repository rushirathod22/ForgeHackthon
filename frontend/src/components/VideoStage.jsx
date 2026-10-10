import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause, FastForward, Maximize2, Shield, Eye, Layers, Camera } from 'lucide-react';

export function VideoStage({ currentTimestamp = 0, activeResult = null }) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [currentTime, setCurrentTime] = useState(currentTimestamp);
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true);
  const [showTrajectories, setShowTrajectories] = useState(true);
  const canvasRef = useRef(null);

  // Sync internal timestamp when an active result card is clicked
  useEffect(() => {
    if (currentTimestamp !== undefined) {
      setCurrentTime(currentTimestamp);
    }
  }, [currentTimestamp]);

  // Simulate video playback timer
  useEffect(() => {
    let interval;
    if (isPlaying) {
      interval = setInterval(() => {
        setCurrentTime((prev) => {
          if (prev >= 300) return 0;
          return prev + 0.1 * playbackRate;
        });
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, playbackRate]);

  // Render bounding box canvas overlay
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    if (!showBoundingBoxes) return;

    // Simulate animated bounding boxes based on currentTime
    const boxOffset = (currentTime * 40) % width;
    
    // Sample Bounding Box 1: Car
    const x1 = (120 + boxOffset * 0.8) % (width - 150);
    const y1 = 180 + Math.sin(currentTime) * 10;
    const w1 = 160;
    const h1 = 100;

    // Box 1 Styling
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.strokeRect(x1, y1, w1, h1);

    ctx.fillStyle = 'rgba(6, 182, 212, 0.2)';
    ctx.fillRect(x1, y1, w1, h1);

    // Label Badge
    ctx.fillStyle = '#06b6d4';
    ctx.fillRect(x1, y1 - 22, 140, 22);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.fillText(`Track #1024 (car - 94%)`, x1 + 6, y1 - 6);

    // Trajectory trail
    if (showTrajectories) {
      ctx.beginPath();
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.moveTo(x1 + w1 / 2, y1 + h1 / 2);
      ctx.lineTo(x1 + w1 / 2 - 80, y1 + h1 / 2 - 20);
      ctx.lineTo(x1 + w1 / 2 - 160, y1 + h1 / 2 - 40);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Sample Bounding Box 2: Truck (if active result or timestamp matches)
    const x2 = (width - 250 - boxOffset * 0.5) % (width - 200);
    const y2 = 240;
    const w2 = 220;
    const h2 = 140;

    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2;
    ctx.strokeRect(x2, y2, w2, h2);

    ctx.fillStyle = 'rgba(16, 185, 129, 0.15)';
    ctx.fillRect(x2, y2, w2, h2);

    ctx.fillStyle = '#10b981';
    ctx.fillRect(x2, y2 - 22, 150, 22);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(`Track #884 (truck - 91%)`, x2 + 6, y2 - 6);

  }, [currentTime, showBoundingBoxes, showTrajectories]);

  const togglePlayback = () => setIsPlaying(!isPlaying);
  const cyclePlaybackRate = () => {
    const rates = [1, 2, 4];
    const nextIndex = (rates.indexOf(playbackRate) + 1) % rates.length;
    setPlaybackRate(rates[nextIndex]);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  };

  return (
    <div className="glass-panel video-card">
      <div className="video-header">
        <div className="video-title">
          <Camera size={18} className="text-cyan" />
          <span>CAM_GATE_01 — South Security Entrance Archive</span>
          <span className="badge badge-cyan">1080p @ 30FPS</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className={`pill-btn ${showBoundingBoxes ? 'badge-cyan' : ''}`}
            onClick={() => setShowBoundingBoxes(!showBoundingBoxes)}
          >
            <Layers size={13} style={{ display: 'inline', marginRight: 4 }} />
            Boxes
          </button>
          <button
            className={`pill-btn ${showTrajectories ? 'badge-amber' : ''}`}
            onClick={() => setShowTrajectories(!showTrajectories)}
          >
            <Eye size={13} style={{ display: 'inline', marginRight: 4 }} />
            Trails
          </button>
        </div>
      </div>

      <div className="video-container">
        {/* Simulated CCTV Video Background */}
        <div
          style={{
            width: '100%',
            height: '100%',
            background: 'radial-gradient(circle, #1a243b 0%, #070a11 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative'
          }}
        >
          {/* CCTV Grid Lines */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: 'linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px)',
              backgroundSize: '40px 40px',
              pointerEvents: 'none'
            }}
          />

          {/* CCTV Camera Info Overlay */}
          <div
            style={{
              position: 'absolute',
              top: 12,
              left: 14,
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              color: 'rgba(255,255,255,0.7)',
              background: 'rgba(0,0,0,0.6)',
              padding: '4px 8px',
              borderRadius: 4
            }}
          >
            REC ● 2026-08-23 14:22:10 UTC | CAM-SOUTH-01
          </div>

          <canvas
            ref={canvasRef}
            width={800}
            height={450}
            className="canvas-overlay"
          />
        </div>
      </div>

      {/* Video Playback Scrubber & Controls */}
      <div className="video-controls">
        <div className="control-group">
          <button className="icon-btn" onClick={togglePlayback}>
            {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <button className="icon-btn" onClick={cyclePlaybackRate}>
            <FastForward size={18} />
            <span style={{ fontSize: '0.75rem', marginLeft: 2, fontWeight: 700 }}>
              {playbackRate}x
            </span>
          </button>
          <span className="time-display">{formatTime(currentTime)} / 05:00.00</span>
        </div>

        <input
          type="range"
          min="0"
          max="300"
          step="0.1"
          value={currentTime}
          onChange={(e) => setCurrentTime(parseFloat(e.target.value))}
          style={{ flex: 1, margin: '0 16px', accentColor: 'var(--accent-cyan)' }}
        />

        <div className="control-group">
          <button className="icon-btn">
            <Maximize2 size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

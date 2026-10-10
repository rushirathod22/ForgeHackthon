import React, { useEffect, useState } from 'react';
import { Camera, Sparkles, CheckCircle2, AlertCircle, Scan, Zap } from 'lucide-react';

const NODE_COORDS = [
  { x: 50, y: 48 },
  { x: 22, y: 32 },
  { x: 78, y: 28 },
  { x: 20, y: 68 },
  { x: 78, y: 72 },
  { x: 38, y: 84 },
  { x: 62, y: 84 },
];

export const fallbackCameraNodes = [
  { id: 'CAM_01', name: 'Main Gate Perimeter', location: 'Gate Entrance', x: 22, y: 32, status: 'STANDBY', scanText: 'MONITORING' },
  { id: 'CAM_02', name: 'Parking Lot North', location: 'North Yard', x: 78, y: 28, status: 'STANDBY', scanText: 'MONITORING' },
  { id: 'CAM_03', name: 'Reception Foyer', location: 'Building A', x: 20, y: 68, status: 'STANDBY', scanText: 'MONITORING' },
  { id: 'CAM_04', name: 'Main Gate Checkpoint', location: 'Main Entrance', x: 50, y: 48, status: 'STANDBY', scanText: 'MONITORING', time: '--:--', matchConfidence: 0, isStrongest: false },
  { id: 'CAM_06', name: 'Executive Lobby', location: 'Building B', x: 78, y: 72, status: 'STANDBY', scanText: 'MONITORING' },
  { id: 'CAM_08', name: 'East Corridor', location: 'Hallway 2', x: 38, y: 84, status: 'STANDBY', scanText: 'MONITORING' },
  { id: 'CAM_11', name: 'Warehouse Loading Bay', location: 'Zone C', x: 62, y: 84, status: 'STANDBY', scanText: 'MONITORING' }
];

export function CameraUniverse({
  isSearching,
  activeSearchResult = null,
  videosList = [],
  onSelectMatch,
  onTransitionComplete,
}) {
  const [scanStep, setScanStep] = useState(0); // 0: Idle/Initial, 1: Signal pulses active, 2: Nodes scanning, 3: Match identified
  const [expandingNode, setExpandingNode] = useState(null);

  const isRealMatch = activeSearchResult && !activeSearchResult.is_no_match && activeSearchResult.confidence > 0 && activeSearchResult.event_type !== 'NO_MATCH';

  const dynamicNodes = React.useMemo(() => {
    if (videosList && videosList.length > 0) {
      return videosList.slice(0, 7).map((vid, idx) => {
        const coords = NODE_COORDS[idx] || { x: 30 + (idx * 10), y: 40 + (idx * 5) };
        const isTargetMatch = isRealMatch && (
          activeSearchResult.video_id === vid.id ||
          activeSearchResult.video_filename === vid.filename ||
          (idx === 0 && !activeSearchResult.video_id)
        );

        return {
          id: `CAM_${vid.id.slice(0, 4).toUpperCase()}`,
          name: vid.filename,
          location: `Channel ${idx + 1}`,
          x: coords.x,
          y: coords.y,
          status: isTargetMatch ? 'MATCH_FOUND' : 'NO_MATCH',
          scanText: isTargetMatch
            ? `✦ MATCH FOUND (${(activeSearchResult.confidence * 100).toFixed(1)}%)`
            : 'NO MATCH FOUND',
          time: isTargetMatch && activeSearchResult.start_time_sec !== undefined
            ? `${Math.floor(activeSearchResult.start_time_sec / 60).toString().padStart(2, '0')}:${Math.floor(activeSearchResult.start_time_sec % 60).toString().padStart(2, '0')}`
            : '--:--',
          matchConfidence: isTargetMatch ? Math.round(activeSearchResult.confidence * 1000) / 10 : 0,
          isStrongest: isTargetMatch,
        };
      });
    }

    return fallbackCameraNodes.map((node) => {
      if (node.isStrongest) {
        if (!isRealMatch) {
          return { ...node, status: 'NO_MATCH', scanText: 'NO MATCH FOUND', isStrongest: false };
        }
        return {
          ...node,
          name: activeSearchResult.video_filename || node.name,
          matchConfidence: Math.round(activeSearchResult.confidence * 1000) / 10,
          scanText: `✦ MATCH FOUND (${(activeSearchResult.confidence * 100).toFixed(1)}%)`,
          time: activeSearchResult.start_time_sec !== undefined
            ? `${Math.floor(activeSearchResult.start_time_sec / 60).toString().padStart(2, '0')}:${Math.floor(activeSearchResult.start_time_sec % 60).toString().padStart(2, '0')}`
            : node.time,
        };
      }
      return node;
    });
  }, [videosList, activeSearchResult, isRealMatch]);

  useEffect(() => {
    if (isSearching) {
      setScanStep(1);
      const timer1 = setTimeout(() => setScanStep(2), 1000);
      const timer2 = setTimeout(() => {
        setScanStep(3);
        // Automatically transition after scan finishes
        setTimeout(() => {
          const matchNode = dynamicNodes.find((n) => n.isStrongest) || dynamicNodes[0];
          if (onTransitionComplete) onTransitionComplete(matchNode);
        }, 1200);
      }, 2500);

      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
      };
    } else {
      setScanStep(3);
    }
  }, [isSearching, dynamicNodes, onTransitionComplete]);

  const handleNodeClick = (node) => {
    setExpandingNode(node.id);
    setTimeout(() => {
      if (onSelectMatch) onSelectMatch(node);
      if (onTransitionComplete) onTransitionComplete(node);
    }, 700);
  };

  return (
    <div className="camera-universe-container">
      {/* Background Neural Constellation Lines (SVG) */}
      <svg className="universe-canvas-lines" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(139, 92, 246, 0.5)" />
            <stop offset="50%" stopColor="rgba(6, 182, 212, 0.8)" />
            <stop offset="100%" stopColor="rgba(99, 102, 241, 0.4)" />
          </linearGradient>

          <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Lines from ASK Central Core (50, 20) to each camera node */}
        {dynamicNodes.map((node) => (
          <g key={`line-group-${node.id}`}>
            <line
              x1="50"
              y1="18"
              x2={node.x}
              y2={node.y}
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="0.5"
            />

            {/* Glowing Active Signal Pulse */}
            {scanStep >= 1 && (
              <line
                x1="50"
                y1="18"
                x2={node.x}
                y2={node.y}
                stroke={node.isStrongest ? '#06B6D4' : 'url(#lineGrad)'}
                strokeWidth={node.isStrongest && scanStep === 3 ? '1.2' : '0.8'}
                strokeDasharray="4 6"
                filter="url(#glowEffect)"
                className="animated-neural-pulse"
              />
            )}
          </g>
        ))}

        {/* Cross-connect nodes for organic mesh feel */}
        <line x1="22" y1="32" x2="50" y2="48" stroke="rgba(255,255,255,0.04)" strokeWidth="0.4" />
        <line x1="78" y1="28" x2="50" y2="48" stroke="rgba(255,255,255,0.04)" strokeWidth="0.4" />
        <line x1="20" y1="68" x2="50" y2="48" stroke="rgba(255,255,255,0.04)" strokeWidth="0.4" />
        <line x1="78" y1="72" x2="50" y2="48" stroke="rgba(255,255,255,0.04)" strokeWidth="0.4" />
        <line x1="38" y1="84" x2="62" y2="84" stroke="rgba(255,255,255,0.04)" strokeWidth="0.4" />
      </svg>

      {/* Central ASK Core Identifier */}
      <div className="universe-central-core">
        <div className="core-beacon-dot"></div>
        <div className="core-label">ASK AI NEURAL HUB</div>
        <div className="core-sublabel">
          {scanStep === 1 && 'DISPATCHING SEARCH SIGNALS...'}
          {scanStep === 2 && 'ANALYZING MULTI-CAMERA STREAM...'}
          {scanStep === 3 && (activeSearchResult ? `MATCH IDENTIFIED ON ${activeSearchResult.video_filename ? activeSearchResult.video_filename.slice(0, 20) : 'CAMERA STREAM'}` : '7 MATCHES LOCATED ACROSS 4 CAMERAS')}
        </div>
      </div>

      {/* Camera Nodes */}
      <div className="camera-nodes-layer">
        {dynamicNodes.map((node) => {
          const isExpanding = expandingNode === node.id;
          const isTarget = node.isStrongest;

          return (
            <div
              key={node.id}
              className={`camera-node-item ${node.status.toLowerCase()} ${
                isTarget ? 'strongest-match' : ''
              } ${isExpanding ? 'signature-expansion' : ''} ${
                scanStep === 3 && !isTarget ? 'dimmed-node' : ''
              }`}
              style={{
                left: `${node.x}%`,
                top: `${node.y}%`,
              }}
              onClick={() => handleNodeClick(node)}
            >
              <div className="node-pulse-ring"></div>

              <div className="node-badge">
                <Camera size={14} className="node-icon" />
                <span className="mono">{node.id}</span>
              </div>

              <div className="node-info-box">
                <div className="node-title">{node.name}</div>

                {scanStep === 1 && (
                  <div className="node-status-line scanning">
                    <Scan size={12} className="spin-icon" />
                    <span>SCANNING FOOTAGE...</span>
                  </div>
                )}

                {scanStep === 2 && (
                  <div className="node-status-line analyzing">
                    <Zap size={12} className="pulse-icon" />
                    <span>SEARCHING FOR HELMET...</span>
                  </div>
                )}

                {scanStep === 3 && (
                  <div className={`node-status-line ${node.status.toLowerCase()}`}>
                    {node.isStrongest ? (
                      <>
                        <Sparkles size={12} className="sparkle-gold" />
                        <span className="match-tag">MATCH FOUND • {node.matchConfidence}%</span>
                      </>
                    ) : node.status === 'POSSIBLE_MATCH' ? (
                      <>
                        <AlertCircle size={12} />
                        <span>POSSIBLE MATCH</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 size={12} />
                        <span>NO MATCH</span>
                      </>
                    )}
                  </div>
                )}

                {scanStep === 3 && node.isStrongest && (
                  <div className="node-action-prompt">
                    <span>Click node to reveal CCTV evidence ➔</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Floating Network Scan Status Badge */}
      <div className="universe-status-overlay">
        <div className="status-pill-glass">
          <div className="pulse-live"></div>
          <span>ACTIVE MONITORING NETWORK: 16 CAMERAS ONLINE</span>
        </div>
      </div>
    </div>
  );
}

export default CameraUniverse;

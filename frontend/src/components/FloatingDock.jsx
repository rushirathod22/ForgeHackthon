import React from 'react';
import { Sparkles, Network, Eye, Footprints, PhoneCall, Settings, Play, ChevronRight, ChevronLeft } from 'lucide-react';

export function FloatingDock({
  activeScreen = 1,
  onNavigate,
  onPrevStep,
  onNextStep,
  totalScreens = 8,
}) {
  const dockItems = [
    { id: 1, label: 'ASK', icon: Sparkles },
    { id: 3, label: 'LIVE', icon: Network },
    { id: 4, label: 'EVIDENCE', icon: Eye },
    { id: 6, label: 'JOURNEY', icon: Footprints },
    { id: 8, label: 'CALL AGENT', icon: PhoneCall },
  ];

  return (
    <div className="floating-dock-container">
      {/* Step Flow Story Controller (Left Side) */}
      <div className="dock-step-controller">
        <button
          className="dock-step-btn"
          disabled={activeScreen <= 1}
          onClick={onPrevStep}
          title="Previous Stage"
        >
          <ChevronLeft size={16} />
        </button>

        <div className="dock-step-indicator mono">
          STAGE {activeScreen} / {totalScreens}
        </div>

        <button
          className="dock-step-btn"
          disabled={activeScreen >= totalScreens}
          onClick={onNextStep}
          title="Next Stage"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Main Glass Navigation Items (Center) */}
      <div className="floating-glass-dock">
        {dockItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            activeScreen === item.id ||
            (item.id === 1 && activeScreen <= 2) ||
            (item.id === 4 && activeScreen === 5) ||
            (item.id === 6 && activeScreen === 7);

          return (
            <button
              key={item.id}
              className={`dock-item-btn ${isActive ? 'active' : ''}`}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={18} className="dock-icon" />
              <span className="dock-label mono">{item.label}</span>
              {isActive && <div className="active-glow-dot"></div>}
            </button>
          );
        })}
      </div>

      {/* Quick Settings Icon (Right Side) */}
      <button
        className="dock-settings-btn"
        onClick={() => onNavigate(1)}
        title="Settings & System Hub"
      >
        <Settings size={18} />
      </button>
    </div>
  );
}

export default FloatingDock;

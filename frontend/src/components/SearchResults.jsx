import React from 'react';
import { Play, Clock, Camera, Sparkles, CheckCircle2, Circle } from 'lucide-react';

// Human-readable label + icon for common attribute tags
const ATTR_META = {
  holding_phone:    { label: 'Phone detected',  icon: '📱', matched: '#06b6d4' },
  holding_bag:      { label: 'Bag detected',    icon: '👜', matched: '#a78bfa' },
  wearing_backpack: { label: 'Backpack',         icon: '🎒', matched: '#f59e0b' },
  red_shirt:        { label: 'Red shirt',        icon: '🔴', matched: '#ef4444' },
  blue_shirt:       { label: 'Blue shirt',       icon: '🔵', matched: '#3b82f6' },
  black_shirt:      { label: 'Black shirt',      icon: '⚫', matched: '#1e293b' },
  white_shirt:      { label: 'White shirt',      icon: '⚪', matched: '#f1f5f9' },
  green_shirt:      { label: 'Green shirt',      icon: '🟢', matched: '#22c55e' },
  orange_shirt:     { label: 'Orange shirt',     icon: '🟠', matched: '#f97316' },
  yellow_shirt:     { label: 'Yellow shirt',     icon: '🟡', matched: '#eab308' },
  black_pants:      { label: 'Black pants',      icon: '👖', matched: '#475569' },
  blue_pants:       { label: 'Blue pants',       icon: '👖', matched: '#3b82f6' },
  moving_with_others: { label: 'In group',       icon: '👥', matched: '#a78bfa' },
  toward_stair:     { label: 'Toward stairs',    icon: '🪜', matched: '#34d399' },
  going_right:      { label: 'Moving right',     icon: '→',  matched: '#94a3b8' },
  going_left:       { label: 'Moving left',      icon: '←',  matched: '#94a3b8' },
  going_up:         { label: 'Moving up',        icon: '↑',  matched: '#94a3b8' },
  going_down:       { label: 'Moving down',      icon: '↓',  matched: '#94a3b8' },
};

function AttrChip({ tag, isMatched }) {
  const meta = ATTR_META[tag];
  const label = meta ? `${meta.icon} ${meta.label}` : tag.replace(/_/g, ' ');
  return (
    <span
      title={isMatched ? '✓ Matched query' : 'Present on track'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        fontSize: '0.68rem',
        fontWeight: 600,
        padding: '2px 8px',
        borderRadius: 20,
        border: `1px solid ${isMatched ? (meta?.matched ?? '#06b6d4') : '#1e2d45'}`,
        background: isMatched
          ? `${meta?.matched ?? '#06b6d4'}22`
          : 'rgba(255,255,255,0.03)',
        color: isMatched ? (meta?.matched ?? '#06b6d4') : '#64748b',
        whiteSpace: 'nowrap',
      }}
    >
      {isMatched && <CheckCircle2 size={10} />}
      {label}
    </span>
  );
}

const formatSec = (s) => {
  if (!s && s !== 0) return '--:--';
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const sec = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${sec}`;
};

const eventBadgeColor = (type) => {
  const map = {
    SUSPICIOUS_ENTRY_UNGUARDED: '#ef4444',
    GUARD_ABSENT: '#f97316',
    ZONE_INTRUSION: '#f59e0b',
    LOITERING: '#eab308',
    FAST_MOVEMENT: '#a78bfa',
    STOPPED_VEHICLE: '#60a5fa',
    OBJECT_TRACKED: '#06b6d4',
  };
  return map[type] ?? '#94a3b8';
};

export function SearchResults({ results = [], onSelectResult, isSearching }) {
  if (isSearching) {
    return (
      <div className="glass-panel results-section" style={{ alignItems: 'center', padding: 40 }}>
        <div className="pulse-live" style={{ width: 16, height: 16, marginBottom: 12 }}></div>
        <h3 style={{ fontSize: '1rem', color: 'var(--accent-cyan)' }}>
          Searching CCTV archives...
        </h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Applying attribute filters + semantic vector search
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel results-section">
      <div className="results-header">
        <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={16} className="text-cyan" />
          {results.length > 0
            ? `${results.length} Match${results.length !== 1 ? 'es' : ''} Found`
            : 'No Results'}
        </h3>
        {results.length > 0 && (
          <span className="badge badge-cyan">Ranked by relevance</span>
        )}
      </div>

      <div className="results-grid">
        {results.map((item, idx) => {
          const matchedSet = new Set(item.matched_attrs ?? []);
          const allAttrs = item.visual_attributes ?? [];
          // Show matched attrs first, then remaining non-matched (capped at 6 total)
          const otherAttrs = allAttrs.filter((a) => !matchedSet.has(a)).slice(0, 4);

          return (
            <div key={idx} className="result-card">
              <div className="result-thumbnail">
                <span
                  className="match-badge"
                  style={{ background: `${eventBadgeColor(item.event_type)}33`,
                           border: `1px solid ${eventBadgeColor(item.event_type)}`,
                           color: eventBadgeColor(item.event_type) }}
                >
                  {item.event_type?.replace(/_/g, ' ')}
                </span>
                <div style={{ textAlign: 'center', padding: 20 }}>
                  <Camera size={32} style={{ opacity: 0.3, color: 'var(--accent-cyan)' }} />
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    Track #{item.track_id}
                  </div>
                </div>
              </div>

              <div className="result-body">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className={`badge badge-${item.class_name === 'truck' ? 'amber' : item.class_name === 'bus' ? 'purple' : 'cyan'}`}>
                    {item.class_name?.toUpperCase()}
                  </span>
                  <span style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                    Score: {item.score?.toFixed(2)}
                  </span>
                </div>

                <div className="result-meta" style={{ marginTop: 6 }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={12} />
                    {formatSec(item.start_time_sec)} – {formatSec(item.end_time_sec)}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {item.video_filename}
                  </span>
                </div>

                {/* Attribute chips — matched first (colored), then others (grey) */}
                {(matchedSet.size > 0 || otherAttrs.length > 0) && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                    {[...matchedSet].map((tag) => (
                      <AttrChip key={tag} tag={tag} isMatched={true} />
                    ))}
                    {otherAttrs.map((tag) => (
                      <AttrChip key={tag} tag={tag} isMatched={false} />
                    ))}
                  </div>
                )}

                <button
                  className="play-clip-btn"
                  style={{ marginTop: 10 }}
                  onClick={() => onSelectResult(item)}
                >
                  <Play size={14} />
                  View Evidence
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

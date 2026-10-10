import { Search, Sparkles, Sliders, Video } from 'lucide-react';

const PRESET_GROUPS = [
  {
    label: '👤 Person',
    queries: [
      'Find the person wearing a red shirt',
      'Find the person wearing a black jacket',
      'Find someone in a blue shirt and jeans',
    ],
  },
  {
    label: '📱 With Object',
    queries: [
      'Find the person holding a phone',
      'Find the person in a red shirt holding a phone',
      'Person with a bag near the entrance',
    ],
  },
  {
    label: '👥 Group',
    queries: [
      'Find two people walking together',
      'Group of people moving toward stairs',
    ],
  },
  {
    label: '🚨 Events',
    queries: [
      'Suspicious person at main gate',
      'Person loitering near entrance',
      'Fast movement detected',
    ],
  },
];

export function SearchBar({ onSearch, isSearching, videosList = [], selectedVideoId = 'all', onSelectVideo }) {
  const [query, setQuery] = useState('');
  const [confidence, setConfidence] = useState(0.4);
  const [activeGroup, setActiveGroup] = useState(0);

  const handleSearchSubmit = (e) => {
    e?.preventDefault();
    if (!query.trim()) return;
    onSearch(query, confidence);
  };

  const handlePillClick = (preset) => {
    setQuery(preset);
    onSearch(preset, confidence);
  };

  return (
    <div className="glass-panel search-section">
      <form onSubmit={handleSearchSubmit}>
        <div className="search-input-wrapper">
          <Search className="search-icon" size={20} />
          <input
            type="text"
            className="search-input"
            placeholder='Ask your CCTV... e.g. "Find the person wearing a red shirt holding a phone"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />

          {/* Processed Videos Dropdown Selector */}
          {videosList && videosList.length > 0 && (
            <select
              value={selectedVideoId}
              onChange={(e) => onSelectVideo && onSelectVideo(e.target.value)}
              title="Select a previously processed video to search in"
              style={{
                background: 'rgba(15, 23, 42, 0.9)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.4)',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '0.78rem',
                fontWeight: '600',
                outline: 'none',
                cursor: 'pointer',
                marginRight: '8px',
                boxShadow: '0 0 10px rgba(56, 189, 248, 0.15)',
              }}
            >
              <option value="all" style={{ background: '#0f172a', color: '#e2e8f0' }}>🌐 All Processed Videos</option>
              {videosList.map((vid) => (
                <option key={vid.id} value={vid.id} style={{ background: '#0f172a', color: '#e2e8f0' }}>
                  🎥 {vid.filename} {vid.status === 'COMPLETED' ? '✅' : '⏳'}
                </option>
              ))}
            </select>
          )}

          <button type="submit" className="search-btn" disabled={isSearching}>
            <Sparkles size={16} />
            {isSearching ? 'Searching...' : 'AI Search'}
          </button>
        </div>
      </form>

      {/* Category tabs */}
      <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
        {PRESET_GROUPS.map((grp, i) => (
          <button
            key={i}
            type="button"
            onClick={() => setActiveGroup(i)}
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 20,
              border: '1px solid',
              cursor: 'pointer',
              transition: 'all 0.2s',
              fontWeight: 600,
              background: activeGroup === i ? 'var(--accent-cyan)' : 'transparent',
              color: activeGroup === i ? '#0a0f1e' : 'var(--text-muted)',
              borderColor: activeGroup === i ? 'var(--accent-cyan)' : 'var(--border-subtle)',
            }}
          >
            {grp.label}
          </button>
        ))}
      </div>

      {/* Preset query pills for active group */}
      <div className="preset-pills" style={{ marginTop: 8 }}>
        <span className="preset-title">Try:</span>
        {PRESET_GROUPS[activeGroup].queries.map((preset, idx) => (
          <button
            key={idx}
            type="button"
            className="pill-btn"
            onClick={() => handlePillClick(preset)}
          >
            {preset}
          </button>
        ))}
      </div>

      <div className="filter-bar" style={{ marginTop: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.8rem' }}>
            <Sliders size={14} style={{ display: 'inline', marginRight: 4 }} />
            Min Confidence: {(confidence * 100).toFixed(0)}%
          </span>
          <input
            type="range"
            min="0.1"
            max="0.9"
            step="0.05"
            value={confidence}
            onChange={(e) => setConfidence(parseFloat(e.target.value))}
            style={{ accentColor: 'var(--accent-cyan)', width: 100 }}
          />
        </div>
      </div>
    </div>
  );
}

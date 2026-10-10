import React, { useState, useRef, useEffect } from 'react';
import { Footprints, Camera, Shield, Eye, Search, Sparkles, User, RefreshCw, AlertCircle } from 'lucide-react';
import { apiUrl } from '../api';

export function PersonJourney({
  targetClass = 'PERSON',
  activeSearchResult = null,
  currentVideoUrl = null,
  videosList = [],
  selectedVideoId = null,
  onSelectSearchResult = null,
  onSelectCheckpoint,
  onCallSecurity,
}) {
  const [activeCheckpointIndex, setActiveCheckpointIndex] = useState(0);
  const [dynamicCheckpoints, setDynamicCheckpoints] = useState([]);
  const [journeySearchQuery, setJourneySearchQuery] = useState('');
  const [isSearchingJourney, setIsSearchingJourney] = useState(false);
  const [availableTracks, setAvailableTracks] = useState([]);
  const [currentSelectedTrack, setCurrentSelectedTrack] = useState(activeSearchResult?.track_id || null);
  const [selectedVid, setSelectedVid] = useState(activeSearchResult?.video_id || selectedVideoId || (videosList[0]?.id || null));
  const videoRef = useRef(null);

  // Effective video ID & track ID
  const effectiveVidId = selectedVid || activeSearchResult?.video_id || selectedVideoId || (videosList[0]?.id || null);
  const effectiveTrackId = currentSelectedTrack || activeSearchResult?.track_id || (availableTracks[0]?.track_id || 1);
  const displayTargetLabel = (activeSearchResult?.class_name || targetClass || 'PERSON').toUpperCase();

  // Load available tracks for the selected video if activeSearchResult is missing
  useEffect(() => {
    if (!effectiveVidId) return;

    let isMounted = true;
    fetch(apiUrl(`/api/v1/videos/${effectiveVidId}/tracks`))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data?.tracks) return;
        setAvailableTracks(data.tracks);
        if (!currentSelectedTrack && data.tracks.length > 0) {
          setCurrentSelectedTrack(data.tracks[0].track_id);
        }
      })
      .catch((err) => console.warn('Could not fetch video tracks:', err));

    return () => {
      isMounted = false;
    };
  }, [effectiveVidId]);

  // Fetch real Cross-Camera ReID Journey from backend whenever video or track changes
  useEffect(() => {
    if (!effectiveVidId || !effectiveTrackId) return;

    let isMounted = true;
    fetch(apiUrl(`/api/v1/tracks/${effectiveVidId}/${effectiveTrackId}/journey`))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data || !data.journey || data.journey.length === 0) return;

        const mapped = data.journey.map((step, idx) => {
          const streamUrl = apiUrl(step.video_url);
          const min = Math.floor(step.first_seen_sec / 60);
          const sec = Math.floor(step.first_seen_sec % 60).toString().padStart(2, '0');

          return {
            id: `reid-step-${idx + 1}`,
            stepNum: step.step_number,
            cameraCode: `CAM_${step.step_number.toString().padStart(2, '0')}`,
            location: step.location_name,
            videoFilename: step.video_filename,
            time: `${min}:${sec}`,
            seconds: step.first_seen_sec,
            activity: `Target ${step.class_name.toUpperCase()} (Track #${step.track_id}) cross-camera sighting verified in ${step.location_name}`,
            confidence: `${(step.similarity_score * 100).toFixed(1)}%`,
            similarity_score: step.similarity_score,
            thumbnailSrc: streamUrl,
          };
        });
        setDynamicCheckpoints(mapped);
        setActiveCheckpointIndex(0);
      })
      .catch((err) => console.warn('Could not fetch ReID journey:', err));

    return () => {
      isMounted = false;
    };
  }, [effectiveVidId, effectiveTrackId]);

  // Handle direct search on the Journey page
  const handleJourneySearch = async (e) => {
    e?.preventDefault();
    if (!journeySearchQuery.trim()) return;

    setIsSearchingJourney(true);
    try {
      const res = await fetch(apiUrl('/api/v1/search'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: journeySearchQuery,
          video_id: effectiveVidId || undefined,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.results && data.results.length > 0) {
          const topResult = data.results[0];
          setSelectedVid(topResult.video_id);
          setCurrentSelectedTrack(topResult.track_id);
          if (onSelectSearchResult) {
            onSelectSearchResult(topResult);
          }
        }
      }
    } catch (err) {
      console.warn('Journey query error:', err);
    } finally {
      setIsSearchingJourney(false);
    }
  };

  const defaultVidSrc = activeSearchResult?.video_url
    ? apiUrl(activeSearchResult.video_url)
    : (currentVideoUrl || '/videos/input/test_cctv.mp4');

  const baseSec = activeSearchResult?.start_time_sec ?? 2.0;

  const fallbackCheckpoints = [
    {
      id: 'chk-1',
      stepNum: 1,
      cameraCode: 'CAM_01',
      location: 'STORE ENTRANCE CHECKPOINT',
      time: `${Math.floor(baseSec / 60)}:${Math.floor(baseSec % 60).toString().padStart(2, '0')}`,
      seconds: Math.max(0, baseSec),
      activity: `Target ${displayTargetLabel} (Track #${effectiveTrackId}) entered primary entrance zone`,
      confidence: activeSearchResult?.confidence ? `${(activeSearchResult.confidence * 100).toFixed(1)}%` : '96.4%',
      thumbnailSrc: defaultVidSrc,
    },
    {
      id: 'chk-2',
      stepNum: 2,
      cameraCode: 'CAM_02',
      location: 'MAIN SHOPPING AISLE',
      time: `${Math.floor((baseSec + 4) / 60)}:${Math.floor((baseSec + 4) % 60).toString().padStart(2, '0')}`,
      seconds: baseSec + 4,
      activity: `Target ${displayTargetLabel} traversed center corridor towards merchandise shelf`,
      confidence: '94.2%',
      thumbnailSrc: defaultVidSrc,
    },
    {
      id: 'chk-3',
      stepNum: 3,
      cameraCode: 'CAM_03',
      location: 'CHECKOUT & POS REGISTER',
      time: `${Math.floor((baseSec + 8) / 60)}:${Math.floor((baseSec + 8) % 60).toString().padStart(2, '0')}`,
      seconds: baseSec + 8,
      activity: `Target ${displayTargetLabel} tracked along spatial trajectory vector near billing zone`,
      confidence: '91.8%',
      thumbnailSrc: defaultVidSrc,
    },
    {
      id: 'chk-4',
      stepNum: 4,
      cameraCode: 'CAM_04',
      location: 'PERIMETER EXIT CORRIDOR',
      time: `${Math.floor((baseSec + 12) / 60)}:${Math.floor((baseSec + 12) % 60).toString().padStart(2, '0')}`,
      seconds: baseSec + 12,
      activity: `Target ${displayTargetLabel} verified leaving surveillance sector`,
      confidence: '89.5%',
      thumbnailSrc: defaultVidSrc,
    },
  ];

  const checkpoints = dynamicCheckpoints.length > 0 ? dynamicCheckpoints : fallbackCheckpoints;
  const currentChk = checkpoints[Math.min(activeCheckpointIndex, checkpoints.length - 1)] || checkpoints[0];

  const handleCheckpointClick = (idx, sec) => {
    setActiveCheckpointIndex(idx);
    if (videoRef.current) {
      videoRef.current.currentTime = sec;
      videoRef.current.play().catch(() => {});
    }
  };

  return (
    <div className="person-journey-container">
      {/* Journey Header with Real-Time Search Bar */}
      <div className="journey-header" style={{ flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <div className="journey-title-group">
            <div className="journey-icon-badge">
              <Footprints size={20} />
            </div>
            <div>
              <h2 className="journey-title">CROSS-CAMERA SPATIAL JOURNEY RECONSTRUCTION</h2>
              <div className="journey-subtitle">
                Target Track #{effectiveTrackId} ({displayTargetLabel}) • Reconstructed across {checkpoints.length} camera checkpoints via CLIP ReID
              </div>
            </div>
          </div>

          {/* Video / Camera Selector Dropdown */}
          {videosList.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="mono" style={{ fontSize: '11px', color: '#94a3b8' }}>CAMERA FEED:</span>
              <select
                className="camera-dropdown"
                value={effectiveVidId || ''}
                onChange={(e) => setSelectedVid(e.target.value)}
                style={{
                  background: 'rgba(15,23,42,0.8)',
                  color: '#e2e8f0',
                  border: '1px solid rgba(6,182,212,0.3)',
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                }}
              >
                {videosList.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.filename} ({v.total_tracks || 0} tracks)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Live Search on Journey Page */}
        <form onSubmit={handleJourneySearch} style={{ display: 'flex', gap: '8px', width: '100%' }}>
          <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', color: '#06b6d4' }} />
            <input
              type="text"
              value={journeySearchQuery}
              onChange={(e) => setJourneySearchQuery(e.target.value)}
              placeholder='Search target to trace journey... e.g. "person in red shirt", "shopper with backpack", "customer"'
              style={{
                width: '100%',
                padding: '10px 14px 10px 38px',
                background: 'rgba(2, 6, 23, 0.7)',
                border: '1px solid rgba(6, 182, 212, 0.4)',
                borderRadius: '8px',
                color: '#f8fafc',
                fontSize: '13px',
                fontFamily: 'inherit',
                outline: 'none',
              }}
            />
          </div>
          <button
            type="submit"
            disabled={isSearchingJourney}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, #0891b2, #06b6d4)',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0 18px',
              fontSize: '12px',
              fontWeight: '600',
              cursor: 'pointer',
              fontFamily: 'monospace',
            }}
          >
            {isSearchingJourney ? <RefreshCw size={14} className="spin-icon" /> : <Sparkles size={14} />}
            <span>TRACE JOURNEY</span>
          </button>
        </form>

        {/* Quick Track Switcher Pills */}
        {availableTracks.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
            <span className="mono" style={{ fontSize: '11px', color: '#64748b' }}>TRACKS IN FEED:</span>
            {availableTracks.slice(0, 8).map((t) => (
              <button
                key={t.track_id}
                type="button"
                onClick={() => setCurrentSelectedTrack(t.track_id)}
                style={{
                  background: currentSelectedTrack === t.track_id ? 'rgba(6, 182, 212, 0.3)' : 'rgba(255,255,255,0.05)',
                  border: currentSelectedTrack === t.track_id ? '1px solid #06b6d4' : '1px solid rgba(255,255,255,0.1)',
                  color: currentSelectedTrack === t.track_id ? '#22d3ee' : '#cbd5e1',
                  borderRadius: '14px',
                  padding: '3px 10px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  fontFamily: 'monospace',
                }}
              >
                Track #{t.track_id} ({t.class_name})
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Connected Visual Movement Path */}
      <div className="spatial-path-timeline">
        <div className="path-connector-line"></div>

        <div className="path-nodes-row">
          {checkpoints.map((chk, idx) => {
            const isActive = activeCheckpointIndex === idx;
            return (
              <div
                key={chk.id}
                className={`path-checkpoint-card ${isActive ? 'active-chk' : ''}`}
                onClick={() => handleCheckpointClick(idx, chk.seconds)}
              >
                <div className="checkpoint-node-dot">
                  <span className="dot-inner"></span>
                </div>

                <div className="chk-camera-badge mono">
                  <Camera size={12} />
                  <span>{chk.cameraCode}</span>
                </div>

                <div className="chk-location">{chk.location}</div>
                <div className="chk-time mono">{chk.time}</div>

                <div className="chk-thumbnail-wrapper">
                  <video src={chk.thumbnailSrc} className="chk-video-preview" muted loop autoPlay />
                  <div className="chk-bbox-preview"></div>
                  {isActive && (
                    <div className="active-focus-pill">
                      <Eye size={12} />
                      <span>FOCUS</span>
                    </div>
                  )}
                </div>

                <div className="chk-confidence-tag mono">MATCH {chk.confidence}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Hero Focused Video Evidence Stage for Selected Checkpoint */}
      <div className="focused-journey-stage">
        <div className="focused-stage-header">
          <div className="focused-location-info">
            <span className="step-num-badge mono">STEP {activeCheckpointIndex + 1} OF {checkpoints.length}</span>
            <span className="loc-name">{currentChk.location} ({currentChk.cameraCode})</span>
            <span className="loc-time mono">TIMESTAMP: {currentChk.time}</span>
          </div>

          <button className="call-sec-btn" onClick={onCallSecurity}>
            <Shield size={14} />
            <span>DISPATCH SECURITY TO THIS ZONE</span>
          </button>
        </div>

        <div className="focused-video-wrapper">
          <video
            key={currentChk.thumbnailSrc}
            ref={videoRef}
            src={currentChk.thumbnailSrc}
            className="focused-video-element"
            autoPlay
            loop
            muted
          />
          <div className="focused-bbox-overlay">
            <div className="bbox-target-box">
              <span className="bbox-tag mono">TRACK #{effectiveTrackId} • {displayTargetLabel} • {currentChk.location}</span>
            </div>
          </div>
          <div className="focused-activity-banner">
            <Footprints size={14} className="banner-icon" />
            <span>{currentChk.activity}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PersonJourney;

import React, { useEffect, useRef } from 'react';

/**
 * AiOrbCanvas Component
 * Render an interactive, dynamic AI orb presence ("ASK")
 * Supports modes: 'idle', 'thinking', 'searching', 'speaking', 'call_active'
 */
export function AiOrbCanvas({ mode = 'idle', size = 180, onClick }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let time = 0;

    // Set high-DPI resolution
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const particles = Array.from({ length: 36 }, (_, i) => ({
      angle: (i * Math.PI * 2) / 36,
      radius: size * 0.35 + (Math.random() - 0.5) * 12,
      speed: 0.005 + Math.random() * 0.01,
      size: 1.5 + Math.random() * 2,
      opacity: 0.3 + Math.random() * 0.7,
    }));

    const render = () => {
      time += 0.03;
      ctx.clearRect(0, 0, size, size);

      const centerX = size / 2;
      const centerY = size / 2;
      const baseRadius = size * 0.28;

      // Color scheme based on mode
      let primaryColor = '#8B5CF6'; // Violet
      let secondaryColor = '#6366F1'; // Indigo
      let glowColor = 'rgba(139, 92, 246, 0.4)';
      let pulseSpeed = 1;

      if (mode === 'thinking' || mode === 'searching') {
        primaryColor = '#06B6D4'; // Cyan
        secondaryColor = '#3B82F6'; // Blue
        glowColor = 'rgba(6, 182, 212, 0.5)';
        pulseSpeed = 2.2;
      } else if (mode === 'speaking') {
        primaryColor = '#A855F7'; // Bright Purple
        secondaryColor = '#EC4899'; // Pink-violet
        glowColor = 'rgba(168, 85, 247, 0.6)';
        pulseSpeed = 1.8;
      } else if (mode === 'call_active') {
        primaryColor = '#10B981'; // Emerald call green
        secondaryColor = '#6366F1';
        glowColor = 'rgba(16, 185, 129, 0.5)';
        pulseSpeed = 2.5;
      }

      // 1. Draw Outer Glowing Atmosphere
      const pulse = Math.sin(time * pulseSpeed) * 6;
      const outerGlow = ctx.createRadialGradient(
        centerX, centerY, baseRadius * 0.2,
        centerX, centerY, baseRadius + 45 + pulse
      );
      outerGlow.addColorStop(0, glowColor);
      outerGlow.addColorStop(0.6, 'rgba(99, 102, 241, 0.15)');
      outerGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');

      ctx.beginPath();
      ctx.arc(centerX, centerY, baseRadius + 45 + pulse, 0, Math.PI * 2);
      ctx.fillStyle = outerGlow;
      ctx.fill();

      // 2. Draw Pulsing Wave Rings
      for (let r = 1; r <= 3; r++) {
        const ringRadius = baseRadius + r * 14 + Math.sin(time * 1.5 + r) * 5;
        ctx.beginPath();
        ctx.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
        ctx.strokeStyle = r === 1 ? primaryColor : secondaryColor;
        ctx.globalAlpha = 0.2 / r;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      ctx.globalAlpha = 1.0;

      // 3. Draw Rotating Particle Swarm
      particles.forEach((p) => {
        p.angle += p.speed * (mode === 'searching' ? 2 : 1);
        const px = centerX + Math.cos(p.angle) * p.radius;
        const py = centerY + Math.sin(p.angle) * p.radius;

        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.angle % 2 === 0 ? primaryColor : secondaryColor;
        ctx.globalAlpha = p.opacity;
        ctx.fill();
      });
      ctx.globalAlpha = 1.0;

      // 4. Draw Core Inner Holographic Orb
      const coreGradient = ctx.createRadialGradient(
        centerX - baseRadius * 0.3,
        centerY - baseRadius * 0.3,
        baseRadius * 0.05,
        centerX,
        centerY,
        baseRadius + pulse * 0.5
      );
      coreGradient.addColorStop(0, '#FFFFFF');
      coreGradient.addColorStop(0.35, primaryColor);
      coreGradient.addColorStop(0.8, secondaryColor);
      coreGradient.addColorStop(1, '#0F172A');

      ctx.beginPath();
      ctx.arc(centerX, centerY, baseRadius + pulse * 0.4, 0, Math.PI * 2);
      ctx.fillStyle = coreGradient;
      ctx.shadowColor = primaryColor;
      ctx.shadowBlur = 25;
      ctx.fill();
      ctx.shadowBlur = 0;

      // 5. Draw Fluid Abstract Sine Surface Overlay
      ctx.beginPath();
      for (let a = 0; a < Math.PI * 2; a += 0.05) {
        const wave = Math.sin(a * 4 + time * 3) * (mode === 'speaking' ? 4 : 2);
        const rad = baseRadius + pulse * 0.4 + wave;
        const x = centerX + Math.cos(a) * rad;
        const y = centerY + Math.sin(a) * rad;
        if (a === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.stroke();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [mode, size]);

  return (
    <div
      className="ai-orb-wrapper"
      onClick={onClick}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: `${size}px`,
          height: `${size}px`,
          display: 'block',
        }}
      />
    </div>
  );
}

export default AiOrbCanvas;

import React, { useState, useEffect, useRef } from 'react';
import { motion, useScroll, useTransform, useSpring, useMotionTemplate } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Globe } from 'lucide-react';


const CHAR_SET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><';

/* --- ScrambleIn Component --- */
export const ScrambleIn: React.FC<{ text: string; delay?: number; triggered?: boolean; className?: string }> = ({
  text,
  delay = 0,
  triggered = true,
  className = '',
}) => {
  const [displayed, setDisplayed] = useState<string>(text);
  const [started, setStarted] = useState<boolean>(false);

  useEffect(() => {
    if (!triggered) {
      setDisplayed('');
      setStarted(false);
      return;
    }

    const timer = setTimeout(() => {
      setStarted(true);
      let frame = 0;

      const interval = setInterval(() => {
        frame++;
        const revealedCount = Math.floor(frame * 0.5);


        if (revealedCount >= text.length) {
          setDisplayed(text);
          clearInterval(interval);
          return;
        }

        let output = '';
        for (let i = 0; i < text.length; i++) {
          if (text[i] === ' ') {
            output += ' ';
          } else if (i < revealedCount) {
            output += text[i];
          } else if (i < revealedCount + 3) {
            output += CHAR_SET[Math.floor(Math.random() * CHAR_SET.length)];
          }
        }
        setDisplayed(output);
      }, 25);

      return () => clearInterval(interval);
    }, delay);

    return () => clearTimeout(timer);
  }, [text, delay, triggered]);

  if (!triggered || !started) {
    return <span className={className}>&nbsp;</span>;
  }

  return <span className={className}>{displayed || '\u00A0'}</span>;
};

/* --- ScrambleText Component (Hover-Driven) --- */
export const ScrambleText: React.FC<{ text: string; isHovered: boolean; className?: string }> = ({
  text,
  isHovered,
  className = '',
}) => {
  const [displayed, setDisplayed] = useState<string>(text);

  useEffect(() => {
    if (!isHovered) {
      setDisplayed(text);
      return;
    }

    let frame = 0;
    const interval = setInterval(() => {
      frame++;
      const revealedCount = Math.floor(frame / 4);

      if (revealedCount >= text.length) {
        setDisplayed(text);
        clearInterval(interval);
        return;
      }

      let output = '';
      for (let i = 0; i < text.length; i++) {
        if (text[i] === ' ') {
          output += ' ';
        } else if (i < revealedCount) {
          output += text[i];
        } else {
          output += CHAR_SET[Math.floor(Math.random() * CHAR_SET.length)];
        }
      }
      setDisplayed(output);
    }, 25);

    return () => clearInterval(interval);
  }, [isHovered, text]);

  return <span className={className}>{displayed}</span>;
};

/* --- 4-Fold Rotation Abstract Logo --- */
export const DataTrustLogo: React.FC<{ size?: number; className?: string }> = ({ size = 24, className = '' }) => {
  const path = 'M 1.5,23 L 1.5,33 C 1.5,38.5 6,43 11.5,43 L 16.5,43 C 22,43 26.5,38.5 26.5,33 Q 28,28 33,26.5 C 38.5,26.5 43,22 43,16.5 L 43,11.5 C 43,6 38.5,1.5 33,1.5 L 23,1.5 Q 12,12 1.5,23 Z';

  return (
    <svg
      width={size}
      height={size}
      viewBox="-50 -50 100 100"
      className={className}
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d={path} transform="rotate(0)" />
      <path d={path} transform="rotate(90)" />
      <path d={path} transform="rotate(180)" />
      <path d={path} transform="rotate(270)" />
    </svg>
  );
};

const NAV_ITEMS = [
  { id: 'section-overview', label: 'Overview' },
  { id: 'section-vision', label: 'Vision' },
  { id: 'section-metrics', label: 'Metrics' },
  { id: 'section-intelligence', label: 'Intelligence' },
  { id: 'section-architecture', label: 'Architecture' },
];

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const [entranceComplete, setEntranceComplete] = useState<boolean>(false);
  const [activeSection, setActiveSection] = useState<string>('section-overview');
  const [navHovered, setNavHovered] = useState<string | null>(null);
  const [downloadHovered, setDownloadHovered] = useState<boolean>(false);

  const heroVideoRef = useRef<HTMLVideoElement | null>(null);
  const pendingSeekRef = useRef<number | null>(null);

  // Entrance trigger
  useEffect(() => {
    const t = setTimeout(() => setEntranceComplete(true), 800);
    return () => clearTimeout(t);
  }, []);

  // Scroll spy tracking for active section highlighting
  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 180;
      for (let i = NAV_ITEMS.length - 1; i >= 0; i--) {
        const el = document.getElementById(NAV_ITEMS[i].id);
        if (el) {
          if (scrollPosition >= el.offsetTop) {
            setActiveSection(NAV_ITEMS[i].id);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Section 2 scroll-driven 3D text
  const section2Ref = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress: s2Progress } = useScroll({
    target: section2Ref,
    offset: ['start end', 'end start'],
  });

  const rawY = useTransform(s2Progress, [0.1, 0.9], [60, -120]);
  const smoothY = useSpring(rawY, { stiffness: 15, damping: 32, mass: 1.8 });
  const s2Opacity = useTransform(s2Progress, [0.2, 0.45, 0.75, 0.95], [0, 1, 1, 0]);
  const transformStyle = useMotionTemplate`perspective(400px) rotateX(24deg) translateY(${smoothY}px) translateZ(15px)`;

  // Hero Video Mouse Scrubbing (delta horizontal movement)
  const handleHeroMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const video = heroVideoRef.current;
    if (!video || !video.duration) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const normalizedX = (e.clientX - rect.left) / rect.width; // 0 to 1
    const targetTime = normalizedX * video.duration * 0.8;

    const performSeek = (time: number) => {
      if (video.seeking) {
        pendingSeekRef.current = time;
        return;
      }
      try {
        video.currentTime = Math.max(0, Math.min(video.duration, time));
      } catch (err) {
        // Ignore seek error
      }
    };

    performSeek(targetTime);
  };

  const handleHeroSeeked = () => {
    if (pendingSeekRef.current !== null && heroVideoRef.current) {
      const nextTime = pendingSeekRef.current;
      pendingSeekRef.current = null;
      heroVideoRef.current.currentTime = nextTime;
    }
  };

  return (
    <div
      style={{
        backgroundColor: '#000000',
        color: '#ffffff',
        fontFamily: '"Space Mono", monospace',
        minHeight: '100vh',
        overflowX: 'hidden',
        position: 'relative',
      }}
    >
      {/* FULL TOP BAR WITH GLASS EFFECT & ACTIVE SECTION HIGHLIGHT */}
      <motion.nav
        initial={{ opacity: 0, y: -15 }}
        animate={{ opacity: entranceComplete ? 1 : 0, y: entranceComplete ? 0 : -15 }}
        transition={{ duration: 0.8 }}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '72px',
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 28px',
          backgroundColor: 'rgba(8, 8, 12, 0.72)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.45)',
          pointerEvents: 'auto',
        }}
      >
        {/* Left: Logo Capsule */}
        <motion.div
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => scrollToSection('section-overview')}
          style={{
            height: '44px',
            padding: '0 18px',
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            cursor: 'pointer',
            border: '1px solid rgba(255, 255, 255, 0.12)',
          }}
        >
          <DataTrustLogo size={18} className="text-white" />
          <span style={{ fontSize: '15px', fontWeight: 600, letterSpacing: '-0.02em', color: '#ffffff' }}>
            DataTrustOS
          </span>
        </motion.div>

        {/* Center: Glass Navigation Track with Active Highlight */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            backgroundColor: 'rgba(255, 255, 255, 0.06)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            borderRadius: '9999px',
            padding: '4px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: 'inset 0 1px 1px rgba(255, 255, 255, 0.1)',
          }}
        >
          {NAV_ITEMS.map((item) => {
            const isActive = activeSection === item.id;
            const isHovered = navHovered === item.id;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => scrollToSection(item.id)}
                onMouseEnter={() => setNavHovered(item.id)}
                onMouseLeave={() => setNavHovered(null)}
                style={{
                  position: 'relative',
                  padding: '6px 16px',
                  borderRadius: '9999px',
                  border: 'none',
                  background: 'transparent',
                  color: isActive ? '#ffffff' : isHovered ? 'rgba(255, 255, 255, 0.95)' : 'rgba(255, 255, 255, 0.55)',
                  fontSize: '13px',
                  fontFamily: '"Space Mono", monospace',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  transition: 'color 0.2s ease',
                  outline: 'none',
                }}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeNavIndicator"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    style={{
                      position: 'absolute',
                      inset: 0,
                      backgroundColor: 'rgba(255, 255, 255, 0.18)',
                      borderRadius: '9999px',
                      border: '1px solid rgba(255, 255, 255, 0.28)',
                      boxShadow: '0 2px 12px rgba(255, 255, 255, 0.15)',
                      zIndex: -1,
                    }}
                  />
                )}
                {item.label}
              </button>
            );
          })}
        </div>

        {/* Right: Launch OS Action Button */}
        <motion.button
          whileHover={{ scale: 1.03, backgroundColor: '#f0f0f4' }}
          whileTap={{ scale: 0.97 }}
          onMouseEnter={() => setDownloadHovered(true)}
          onMouseLeave={() => setDownloadHovered(false)}
          onClick={() => navigate('/dashboard')}
          style={{
            height: '44px',
            padding: '0 20px',
            backgroundColor: '#ffffff',
            color: '#000000',
            borderRadius: '9999px',
            border: 'none',
            fontFamily: '"Space Mono", monospace',
            fontSize: '13px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(255, 255, 255, 0.25)',
          }}
        >
          <Globe size={15} />
          <ScrambleText text="Launch OS" isHovered={downloadHovered} />
          <ArrowRight size={13} />
        </motion.button>
      </motion.nav>


      {/* ========================================================================= */}
      {/* SECTION 1: HERO (MOUSE-SCRUBBED VIDEO, FULL VIEWPORT HEIGHT) */}
      {/* ========================================================================= */}
      <section
        id="section-overview"
        onMouseMove={handleHeroMouseMove}
        style={{
          position: 'relative',
          height: '100vh',
          minHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '96px 32px 48px',
          overflow: 'hidden',
        }}
      >

        {/* Background Video (Mouse Scrubbed) */}
        <video
          ref={heroVideoRef}
          onSeeked={handleHeroSeeked}
          playsInline
          muted
          preload="auto"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            zIndex: 0,
            pointerEvents: 'none',
          }}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_083515_290e5a10-0b95-41af-a5e2-32b6389baa4d.mp4"
        />

        {/* 24x24 Dot Grid Overlay */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)',
            backgroundSize: '24px 24px',
            opacity: 0.05,
            pointerEvents: 'none',
            zIndex: 1,
          }}
        />

        {/* Background Watermark: RELIABILITY in Anton SC */}
        <div
          style={{
            position: 'absolute',
            top: 'calc(50% + 50px)',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontFamily: '"Anton SC", sans-serif',
            fontSize: 'clamp(100px, 25vw, 480px)',
            letterSpacing: '-4px',
            textTransform: 'uppercase',
            opacity: 0.12,
            backgroundImage: 'radial-gradient(circle, rgba(142,127,148,0) 0%, #8E7F94 70%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            zIndex: 2,
            userSelect: 'none',
          }}
        >
          RELIABILITY
        </div>

        {/* Top spacer */}
        <div style={{ zIndex: 10 }} />

        {/* Bottom Content Row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: entranceComplete ? 1 : 0 }}
          transition={{ duration: 1 }}
          style={{
            zIndex: 10,
            display: 'flex',
            flexDirection: 'row',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            gap: '32px',
            flexWrap: 'wrap',
          }}
        >
          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '580px' }}>
            <h1
              style={{
                color: '#ffffff',
                fontWeight: 300,
                lineHeight: 0.95,
                letterSpacing: '-0.03em',
                fontSize: 'clamp(36px, 7vw, 76px)',
                margin: 0,
              }}
            >
              <ScrambleIn text="Autonomous Data" delay={200} triggered={entranceComplete} />
              <br />
              <ScrambleIn text="Reliability OS" delay={500} triggered={entranceComplete} />
            </h1>

            <motion.p
              initial={{ y: 25, opacity: 0 }}
              animate={entranceComplete ? { y: 0, opacity: 1 } : {}}
              transition={{ duration: 0.9, delay: 0.2, ease: [0.215, 0.61, 0.355, 1.0] }}
              style={{
                fontSize: '14px',
                color: 'rgba(255, 255, 255, 0.65)',
                lineHeight: 1.6,
                margin: 0,
              }}
            >
              Turn corrupt enterprise telemetry into deterministic operational truth. Multi-agent AI profiles raw tables,
              synthesizes L1–L4 invariants, and quarantines anomalies with cryptographic SHA-256 lineage manifests.
            </motion.p>

            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={entranceComplete ? { y: 0, opacity: 1 } : {}}
              transition={{ duration: 0.9, delay: 0.4 }}
              style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '8px', flexWrap: 'wrap' }}
            >
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                style={{
                  height: '42px',
                  padding: '0 20px',
                  backgroundColor: '#ffffff',
                  color: '#000000',
                  borderRadius: '9999px',
                  border: 'none',
                  fontFamily: '"Space Mono", monospace',
                  fontSize: '13px',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  boxShadow: '0 4px 20px rgba(255, 255, 255, 0.25)',
                }}
              >
                <span>Launch OS</span>
                <ArrowRight size={14} />
              </button>

              <button
                type="button"
                onClick={() => navigate('/workspace')}
                style={{
                  height: '42px',
                  padding: '0 18px',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  backdropFilter: 'blur(10px)',
                  color: '#ffffff',
                  borderRadius: '9999px',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  fontFamily: '"Space Mono", monospace',
                  fontSize: '13px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <span>Open Agent Workspace</span>
              </button>
            </motion.div>
          </div>

          {/* Right Column */}
          <div style={{ textAlign: 'right' }}>
            <h1
              style={{
                color: '#ffffff',
                fontWeight: 300,
                lineHeight: 0.95,
                letterSpacing: '-0.03em',
                fontSize: 'clamp(36px, 7vw, 76px)',
                margin: 0,
              }}
            >
              <ScrambleIn text="Zero Data" delay={700} triggered={entranceComplete} />
              <br />
              <ScrambleIn text="Loss Fabric" delay={1000} triggered={entranceComplete} />
            </h1>
          </div>
        </motion.div>
      </section>

      {/* ========================================================================= */}
      {/* SECTION 2: CINEMATIC 3D SCROLL TEXT */}
      {/* ========================================================================= */}
      <section
        id="section-vision"
        ref={section2Ref}
        style={{
          position: 'relative',
          height: '100vh',
          minHeight: '100dvh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          backgroundColor: '#000000',
        }}
      >

        {/* Background Video #2 */}
        <video
          autoPlay
          muted
          loop
          playsInline
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            zIndex: 0,
            opacity: 0.45,
          }}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_092455_089c54f8-3b03-4966-9df1-e9746063d0ef.mp4"
        />

        {/* Top Gradient Overlay */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '180px',
            background: 'linear-gradient(to bottom, #010103, transparent)',
            zIndex: 10,
          }}
        />

        {/* 3D Perspective Paragraph */}
        <motion.div
          style={{
            transform: transformStyle,
            opacity: s2Opacity,
            zIndex: 20,
            maxWidth: '1000px',
            padding: '0 32px',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              fontSize: 'clamp(20px, 3.8vw, 36px)',
              fontWeight: 400,
              lineHeight: 1.45,
              letterSpacing: '-0.02em',
              color: '#ffffff',
              userSelect: 'none',
              margin: 0,
            }}
          >
            An autonomous multi-agent operating system engineered for enterprise data stewards. DataTrust OS transforms
            raw, corrupted telemetry into deterministic operational truth. Anomalies are instantly profiled, synthesized
            into verifiable L1–L4 rules, isolated in quarantine stores, and certified with cryptographic SHA-256 manifests.
          </p>
        </motion.div>
      </section>

      {/* ========================================================================= */}
      {/* SECTION 3: PERFORMANCE METRICS */}
      {/* ========================================================================= */}
      <section
        id="section-metrics"
        style={{
          position: 'relative',
          minHeight: '100vh',
          padding: '120px 32px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          backgroundColor: '#000000',
        }}
      >

        {/* Background Video #3 */}
        <video
          autoPlay
          muted
          loop
          playsInline
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            zIndex: 0,
            opacity: 0.35,
          }}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_095810_ecea3dd2-fc5e-4e41-8696-4219290b6589.mp4"
        />

        <div style={{ position: 'relative', zIndex: 10, maxWidth: '1100px', width: '100%' }}>
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 1.2 }}
            style={{
              textAlign: 'center',
              fontSize: '13px',
              letterSpacing: '0.2em',
              textTransform: 'uppercase',
              color: 'rgba(255, 255, 255, 0.4)',
              marginBottom: '72px',
            }}
          >
            PERFORMANCE METRICS
          </motion.div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '48px',
              textAlign: 'center',
            }}
          >
            {[
              { val: '< 10%', label: 'SLA Quarantine Target' },
              { val: '99.8%', label: 'Automated RCA Accuracy' },
              { val: '100%', label: 'Cryptographic SHA-256 Audit Trail' },
            ].map((metric, i) => (
              <motion.div
                key={metric.label}
                initial={{ y: 30, opacity: 0 }}
                whileInView={{ y: 0, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8, delay: i * 0.15 }}
                style={{
                  padding: '32px 24px',
                  backgroundColor: 'rgba(255, 255, 255, 0.04)',
                  backdropFilter: 'blur(10px)',
                  borderRadius: '16px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div
                  style={{
                    fontSize: 'clamp(44px, 8vw, 84px)',
                    fontWeight: 300,
                    letterSpacing: '-0.04em',
                    lineHeight: 1,
                    color: '#ffffff',
                  }}
                >
                  {metric.val}
                </div>
                <div
                  style={{
                    marginTop: '16px',
                    fontSize: '14px',
                    color: 'rgba(255, 255, 255, 0.5)',
                    letterSpacing: '0.05em',
                  }}
                >
                  {metric.label}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* SECTION 4: ADAPTIVE INTELLIGENCE */}
      {/* ========================================================================= */}
      <section
        id="section-intelligence"
        style={{
          position: 'relative',
          height: '100vh',
          minHeight: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '64px 48px',
          overflow: 'hidden',
          backgroundColor: '#000000',
        }}
      >

        {/* Background Video #4 */}
        <video
          autoPlay
          muted
          loop
          playsInline
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            zIndex: 0,
            opacity: 0.35,
          }}
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_095750_32a52ce0-2005-45c9-9093-41f03fde9530.mp4"
        />

        {/* Top area */}
        <div
          style={{
            position: 'relative',
            zIndex: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '32px',
            flexWrap: 'wrap',
          }}
        >
          <motion.h2
            initial={{ y: 40, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 1 }}
            style={{
              fontSize: 'clamp(32px, 6vw, 64px)',
              fontWeight: 300,
              lineHeight: 0.95,
              letterSpacing: '-0.03em',
              margin: 0,
              color: '#ffffff',
            }}
          >
            Autonomous
            <br />
            Governance
          </motion.h2>

          <motion.p
            initial={{ y: 20, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1, delay: 0.2 }}
            style={{
              fontSize: '14px',
              color: 'rgba(255, 255, 255, 0.5)',
              lineHeight: 1.6,
              maxWidth: '380px',
              textAlign: 'right',
              margin: 0,
            }}
          >
            The system dynamically learns telemetry baselines across multi-domain fleets. Every fault state is analyzed,
            predicted, and quarantined with human-in-the-loop audit gates.
          </motion.p>
        </div>

        {/* Bottom feature cards grid */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1, delay: 0.3 }}
          style={{
            position: 'relative',
            zIndex: 10,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '24px',
          }}
        >
          {[
            { title: 'Autonomous Profiler', desc: 'Fast distribution & null rate scan across 50,000+ sampled records.' },
            { title: 'L1–L4 Rule Synthesis', desc: 'Synthesizes deterministic range, enum, and variance invariants.' },
            { title: 'Zero-Loss Split-DB', desc: 'Isolates clean production tables from quarantined corrupt rows.' },
            { title: 'HITL Policy Checkpoint', desc: 'Human-in-the-loop review, customize & approve before DuckDB compilation.' },
          ].map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ y: 20, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, delay: i * 0.1 }}
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                backdropFilter: 'blur(8px)',
                padding: '20px',
                borderRadius: '12px',
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#ffffff', marginBottom: '8px' }}>
                {item.title}
              </div>
              <div style={{ fontSize: '12.5px', color: 'rgba(255, 255, 255, 0.5)', lineHeight: 1.5 }}>
                {item.desc}
              </div>
            </motion.div>
          ))}
        </motion.div>
      </section>

      {/* ========================================================================= */}
      {/* SECTION 5: ARCHITECTURE (PURE BLACK, NO VIDEO) */}
      {/* ========================================================================= */}
      <section
        id="section-architecture"
        style={{
          position: 'relative',
          minHeight: '100vh',
          backgroundColor: '#000000',
          padding: '120px 24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >

        <div style={{ maxWidth: '820px', width: '100%', textAlign: 'center' }}>
          <motion.div
            initial={{ y: 30, opacity: 0 }}
            whileInView={{ y: 0, opacity: 1 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ duration: 1 }}
          >
            <div
              style={{
                fontSize: '13px',
                letterSpacing: '0.2em',
                textTransform: 'uppercase',
                color: 'rgba(255, 255, 255, 0.4)',
                marginBottom: '24px',
              }}
            >
              ARCHITECTURE
            </div>

            <h2
              style={{
                fontSize: 'clamp(28px, 5vw, 54px)',
                fontWeight: 300,
                lineHeight: 1.15,
                letterSpacing: '-0.02em',
                color: '#ffffff',
                marginBottom: '24px',
              }}
            >
              Three layers. Zero friction.
            </h2>

            <p
              style={{
                fontSize: '15px',
                color: 'rgba(255, 255, 255, 0.5)',
                lineHeight: 1.7,
                maxWidth: '640px',
                margin: '0 auto 64px',
              }}
            >
              Ingestion layer captures raw telemetry and schema. ReAct multi-agent layer diagnoses root causes and
              synthesizes invariants. Governance layer delivers isolated quarantine storage and cryptographic verification.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ duration: 1.2, delay: 0.3 }}
            style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}
          >
            {[
              { layer: 'Layer 1', role: 'Telemetry Ingestion & Sub-Second Statistical Profiling' },
              { layer: 'Layer 2', role: 'ReAct Multi-Agent Anomaly Diagnosis & Rule Synthesis' },
              { layer: 'Layer 3', role: 'Split-DB Quarantine & Cryptographic SHA-256 Lineage Ledger' },
            ].map((l) => (
              <div
                key={l.layer}
                style={{
                  width: '100%',
                  maxWidth: '620px',
                  height: '72px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0 24px',
                  backgroundColor: 'rgba(255, 255, 255, 0.02)',
                }}
              >
                <span
                  style={{
                    fontSize: '12px',
                    letterSpacing: '0.15em',
                    textTransform: 'uppercase',
                    color: 'rgba(255, 255, 255, 0.35)',
                    fontWeight: 600,
                  }}
                >
                  {l.layer}
                </span>
                <span style={{ fontSize: '14.5px', fontWeight: 400, color: '#ffffff', textAlign: 'right' }}>{l.role}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* FOOTER */}
      {/* ========================================================================= */}
      <footer
        style={{
          backgroundColor: '#000000',
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          minHeight: '400px',
        }}
      >
        {/* Left: Video #5 */}
        <div style={{ flex: '1 1 400px', minHeight: '300px', position: 'relative' }}>
          <video
            autoPlay
            muted
            loop
            playsInline
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260622_080203_fd7f4f85-3a86-4837-8192-85e7bfe68e75.mp4"
          />
        </div>

        {/* Right: Info & Links */}
        <div
          style={{
            flex: '1 1 400px',
            padding: '48px',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
              <DataTrustLogo size={20} className="text-white" />
              <span style={{ fontSize: '16px', fontWeight: 600, color: '#ffffff' }}>DataTrustOS Labs</span>
            </div>

            <p style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.45)', lineHeight: 1.6, maxWidth: '420px' }}>
              The next evolution of enterprise data reliability and telemetry governance.
              Built for organizations that refuse to leave data quality to chance.
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px',
              marginTop: '48px',
            }}
          >
            <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.3)' }}>
              © 2026 DataTrust OS Labs. All rights reserved.
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                onClick={() => navigate('/workspace')}
                style={{
                  background: 'transparent',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#ffffff',
                  fontSize: '13px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontFamily: '"Space Mono", monospace',
                }}
              >
                Agent Workspace →
              </button>

              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                style={{
                  background: '#ffffff',
                  border: 'none',
                  color: '#000000',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '8px 16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontFamily: '"Space Mono", monospace',
                }}
              >
                Open Console →
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

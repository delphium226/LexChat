import { useState, useEffect } from 'react';
import { fetchBotInfo } from '../services/api';

// Bot identity (name/tagline/branding) and favicon behaviour, moved from App.jsx:
// - on mount: fetch /api/bot-info, set document.title, swap favicon to the bot
//   logo (or an emoji canvas fallback)
// - while `loading` is true: animate a spinner favicon; revert on completion
export function useBotIdentity(loading) {
  const [botInfo, setBotInfo] = useState({
    name: 'AILA',
    tagline: 'AI Legal Assistant',
    brandColor: null,
    logoEmoji: null,
    researchMode: '',
  });
  const [botLogoUrl, setBotLogoUrl] = useState(null);

  useEffect(() => {
    fetchBotInfo()
      .then(info => {
        if (info?.name) {
          setBotInfo({
            name: info.name,
            tagline: info.tagline || '',
            brandColor: info.brand_color || null,
            logoEmoji: info.logo_emoji || null,
            researchMode: info.research_mode || '',
          });
          document.title = info.name;
        }
        // Swap favicon to bot logo; fall back to emoji canvas; leave as /favicon.svg if neither
        const favicon = document.querySelector("link[rel='icon']");
        const emoji = info?.logo_emoji || null;
        const img = new Image();
        img.onload = () => {
          if (favicon) favicon.href = '/api/bot/logo';
          setBotLogoUrl('/api/bot/logo');
        };
        img.onerror = () => {
          if (!emoji) return;
          const canvas = document.createElement('canvas');
          canvas.width = 32;
          canvas.height = 32;
          const ctx = canvas.getContext('2d');
          ctx.font = '24px serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(emoji, 16, 17);
          const dataUrl = canvas.toDataURL('image/png');
          if (favicon) favicon.href = dataUrl;
          setBotLogoUrl(dataUrl);
        };
        img.src = '/api/bot/logo';
      })
      .catch(err => console.warn('Failed to fetch bot info:', err));
  }, []);

  // Favicon animation while loading
  useEffect(() => {
    const favicon = document.querySelector("link[rel='icon']");
    if (!favicon) return;
    if (!loading) {
      favicon.href = botLogoUrl || '/favicon.svg';
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = 32;
    canvas.height = 32;
    const ctx = canvas.getContext('2d');
    let animId,
      startTime = null;

    const draw = ts => {
      if (!startTime) startTime = ts;
      const angle = ((ts - startTime) / 700) * Math.PI * 2;
      ctx.clearRect(0, 0, 32, 32);
      ctx.beginPath();
      ctx.arc(16, 16, 12, 0, Math.PI * 2);
      ctx.strokeStyle = '#dbeafe';
      ctx.lineWidth = 3.5;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(16, 16, 12, angle, angle + Math.PI * 1.25);
      ctx.strokeStyle = '#2563eb';
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.stroke();
      favicon.href = canvas.toDataURL('image/png');
      animId = requestAnimationFrame(draw);
    };

    animId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animId);
      favicon.href = botLogoUrl || '/favicon.svg';
    };
  }, [loading, botLogoUrl]);

  return { botInfo, botLogoUrl };
}

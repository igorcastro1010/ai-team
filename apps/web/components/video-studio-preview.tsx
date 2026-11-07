"use client";

import { useEffect, useRef, useState } from "react";
import { contentUrl, duration, previewText, sceneAt, type Media, type StudioDocument } from "@/lib/video-studio";

export function VideoStudioPreview({ document, project, media, time, playing, onTime, onPlaying }: { document: StudioDocument; project: string; media: Media[]; time: number; playing: boolean; onTime: (time: number) => void; onPlaying: (playing: boolean) => void }) {
  const frame = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const [width, setWidth] = useState(260);
  const { scene, local } = sceneAt(document, time);
  const asset = media.find(item => item.id === scene.media_id);
  const total = duration(document);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(entries[0].contentRect.width));
    if (frame.current) observer.observe(frame.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!playing) return;
    let id = 0;
    const started = performance.now();
    const initial = time;
    const tick = (now: number) => {
      const next = Math.min(total, initial + (now - started) / 1000);
      onTime(next);
      if (next >= total) onPlaying(false); else id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
    // Time is sampled at play; subsequent animation frames must not restart the clock.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, total]);
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    const sync = () => {
      const target = local % (Number.isFinite(element.duration) && element.duration > 0 ? element.duration : asset?.duration || scene.duration);
      if (Math.abs(element.currentTime - target) > .15) element.currentTime = target;
      if (playing) void element.play().catch(() => {}); else element.pause();
    };
    sync(); element.addEventListener("loadedmetadata", sync);
    return () => element.removeEventListener("loadedmetadata", sync);
  }, [local, playing, asset?.id, asset?.duration, scene.duration]);
  useEffect(() => {
    const element = audio.current;
    const settings = document.audio;
    if (!element || !settings) return;
    const sync = () => {
      const actualDuration = Number.isFinite(element.duration) && element.duration > 0 ? element.duration : total;
      const target = Math.min(time, actualDuration);
      const fadeIn = Math.min(settings.fade_in, total);
      const fadeOut = Math.min(settings.fade_out, total);
      if (Math.abs(element.currentTime - target) > .15) element.currentTime = target;
      element.volume = time >= actualDuration ? 0 : settings.volume * Math.max(0, Math.min(1, fadeIn ? time / fadeIn : 1, fadeOut ? (total - time) / fadeOut : 1));
      if (playing && time < actualDuration) void element.play().catch(() => {}); else element.pause();
    };
    sync(); element.addEventListener("loadedmetadata", sync);
    return () => element.removeEventListener("loadedmetadata", sync);
  }, [time, playing, document.audio, total]);
  const progress = local / scene.duration;
  const fadeLength = Math.min(.4, scene.duration / 2);
  const fade = Math.max(0, Math.min(1, local / fadeLength, (scene.duration - local) / fadeLength));
  const opacity = scene.transition === "fade" || scene.animation === "fade" ? fade : 1;
  const transform = scene.animation === "zoom" ? `scale(${1 + .08 * progress})` : scene.animation === "pan" ? `translateX(${4 - 8 * progress}%) scale(1.08)` : undefined;
  const textProgress = Math.min(1, local / .4, (scene.duration - local) / .4);
  const readableStill = !playing && (local === 0 || local === scene.duration);
  const slide = 16 * width / 720 * (1 - Math.min(1, local / .4) - (1 - Math.min(1, (scene.duration - local) / .4)));
  return <section className="studio-preview" aria-label="Prévia do vídeo">
    <div className={`studio-stage stage-${document.format}`} ref={frame}>
      <div className="studio-composite" style={{ background: scene.background, opacity: !playing && (local === 0 || local === scene.duration) ? 1 : opacity }}>
        <div className="studio-visual" style={{ transform }}>
          {/* Authenticated local media is served through the same-origin proxy. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {asset?.kind === "image" && <img src={contentUrl(project, asset.id)} alt="Mídia da cena" />}
          {asset?.kind === "video" && <video ref={video} src={contentUrl(project, asset.id)} muted playsInline loop preload="metadata" />}
        </div>
        <div className="studio-text-anchor" style={{ justifyContent: scene.x === 0 ? "flex-start" : scene.x === 100 ? "flex-end" : undefined }}>
          <span style={{ left: `${scene.x}%`, top: `${scene.y}%`, transform: `translate(-${scene.x}%, -${scene.y}%) translateY(${scene.text_animation === "slide" && !readableStill ? slide : 0}px)`, fontFamily: `Studio-${scene.font}`, fontSize: scene.font_size * width / 720, color: scene.color, opacity: scene.text_animation === "none" || readableStill ? 1 : textProgress }}>{previewText(scene.text, document.format)}</span>
        </div>
      </div>
    </div>
    {document.audio && <audio ref={audio} src={contentUrl(project, document.audio.media_id)} preload="metadata" />}
    <div className="studio-transport"><button className="button" type="button" onClick={() => { if (time >= total) onTime(0); onPlaying(!playing); }}>{playing ? "Pausar prévia" : "Reproduzir prévia"}</button><span className="studio-time">{time.toFixed(1)}s / {total}s</span></div>
    <label className="studio-scrub">Posição da prévia<input aria-label="Posição da prévia" type="range" min={0} max={total} step={.05} value={time} onChange={event => { onPlaying(false); onTime(Number(event.target.value)); }} /></label>
    <p className="studio-preview-note">Prévia local · áudio dos clipes silenciado · {document.resolution}. Quadro pausado visível; fades durante a reprodução.</p>
  </section>;
}

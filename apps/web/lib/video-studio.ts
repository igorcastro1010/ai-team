export type Scene = { text: string; duration: number; media_id: string | null; x: number; y: number; font_size: number; color: string; background: string; font: "sans" | "serif" | "mono"; animation: "none" | "fade" | "zoom" | "pan"; text_animation: "none" | "fade" | "slide"; transition: "cut" | "fade" };
export type StudioDocument = { title: string; format: "vertical" | "square" | "horizontal"; resolution: "720p" | "1080p"; scenes: Scene[]; audio: { media_id: string; volume: number; fade_in: number; fade_out: number } | null };
export type Media = { id: string; name: string; kind: "image" | "video" | "audio"; mime: string; bytes: number; sha256: string; duration: number | null; width: number | null; height: number | null };
export type Template = { id: string; name: string; document: StudioDocument };
export const newScene = (): Scene => ({ text: "", duration: 5, media_id: null, x: 50, y: 50, font_size: 36, color: "#ffffff", background: "#13233c", font: "sans", animation: "none", text_animation: "none", transition: "cut" });
export const newDocument = (): StudioDocument => ({ title: "", format: "vertical", resolution: "720p", scenes: [newScene()], audio: null });
export const duration = (document: StudioDocument) => document.scenes.reduce((sum, scene) => sum + scene.duration, 0);
export const contentUrl = (project: string, id: string) => `/api/control/video-studio/${project}/media/${id}/content`;
export function sceneAt(document: StudioDocument, time: number) {
  let start = 0;
  for (let index = 0; index < document.scenes.length; index++) {
    const scene = document.scenes[index];
    if (time < start + scene.duration || index === document.scenes.length - 1) return { scene, index, local: Math.max(0, Math.min(scene.duration, time - start)) };
    start += scene.duration;
  }
  return { scene: document.scenes[0], index: 0, local: 0 };
}
/** Match the renderer's bounded paragraph wrapping at its output width. */
export function previewText(text: string, format: StudioDocument["format"]) {
  const limit = format === "horizontal" ? 48 : 27;
  const lines: string[] = [];
  for (const paragraph of text.split(/\r?\n/)) {
    let line = "";
    const words = paragraph.trim().split(/\s+/).filter(Boolean);
    for (let word of words) {
      if (line && line.length + word.length + 1 > limit) {
        const available = limit - line.length - 1;
        const hyphen = word.lastIndexOf("-", available - 1);
        if (hyphen > 0) { line += ` ${word.slice(0, hyphen + 1)}`; word = word.slice(hyphen + 1); }
        lines.push(line); line = "";
      }
      while (word.length > limit) {
        const hyphen = word.lastIndexOf("-", limit - 1);
        const split = hyphen > 0 ? hyphen + 1 : limit;
        lines.push(word.slice(0, split)); word = word.slice(split);
      }
      if (word) line += `${line ? " " : ""}${word}`;
    }
    if (line) lines.push(line);
  }
  return lines.join("\n");
}

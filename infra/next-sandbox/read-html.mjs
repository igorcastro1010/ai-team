// Preserve multibyte Portuguese characters when HTTP chunks split UTF-8 sequences.
export async function readHtml(body, limit = 524288) {
  const decoder = new TextDecoder();
  let html = "", bytes = 0;
  for await (const chunk of body) {
    bytes += chunk.byteLength;
    if (bytes > limit) throw new Error("HTML limit");
    html += decoder.decode(chunk, { stream: true });
  }
  return html + decoder.decode();
}

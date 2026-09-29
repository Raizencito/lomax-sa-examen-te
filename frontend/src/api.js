export const API = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
export async function api(path, opts = {}) {
  const r = await fetch(`${API}${path}`, opts)
  const txt = await r.text()
  let body
  try { body = txt ? JSON.parse(txt) : {} } catch { body = { raw: txt } }
  return { status: r.status, body }
}
export const imgUrl = (id) => `${API}/productos/${id}/imagen`

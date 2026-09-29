import { useEffect, useState } from 'react'
import { Link, Routes, Route, useParams, useNavigate } from 'react-router-dom'
import { api, imgUrl } from './api.js'

const ATTR_SETS = {
  1: [{ k: 'conexion', label: 'Conexion', ph: 'USB-C / 2.4GHz' }, { k: 'distribucion', label: 'Distribucion', ph: 'ES / US' }, { k: 'retroiluminado', label: 'Retroiluminado', ph: 'RGB / No' }],
  2: [{ k: 'pulgadas', label: 'Pulgadas', ph: '27' }, { k: 'resolucion', label: 'Resolucion', ph: '2560x1440' }, { k: 'tasa_refresco', label: 'Tasa refresco', ph: '165Hz' }],
  3: [{ k: 'tipo', label: 'Tipo', ph: 'Over-ear' }, { k: 'conexion', label: 'Conexion', ph: 'Bluetooth / Jack' }, { k: 'cancelacion_ruido', label: 'Cancelacion ruido', ph: 'Si / No' }],
}

function Registro() {
  const nav = useNavigate()
  const [cats, setCats] = useState([])
  const [form, setForm] = useState({ codigo: '', nombre: '', descripcion: '', precio: '', categoria_id: '1', atributos: {}, })
  const [file, setFile] = useState(null)
  const [msg, setMsg] = useState(null)
  const [pid, setPid] = useState(null)
  useEffect(() => { api('/categorias').then(({ body }) => setCats(body.categorias || [])) }, [])
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const setAttr = (k, v) => setForm(f => ({ ...f, atributos: { ...f.atributos, [k]: v } }))
  async function submit(e) {
    e.preventDefault(); setMsg({ t: 'Registrando producto base...', ok: null })
    const { status, body } = await api('/productos', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, precio: parseFloat(form.precio), categoria_id: parseInt(form.categoria_id) }) })
    if (status !== 201) { setMsg({ t: `Error ${status}: ${JSON.stringify(body)}`, ok: false }); return }
    const id = body.producto_id; setPid(id)
    if (!file) { setMsg({ t: `Producto ${id} PENDIENTE (sin imagen). Sube foto para publicar.`, ok: null }); return }
    await subirImagen(id)
  }
  async function subirImagen(id) {
    const fd = new FormData(); fd.append('imagen', file)
    setMsg({ t: 'Subiendo imagen y generando miniatura...', ok: null })
    const { status, body } = await api(`/productos/${id}/imagen`, { method: 'POST', body: fd })
    if (status === 200 && body.estado === 'PUBLICADO') { setMsg({ t: `Producto ${id} PUBLICADO.`, ok: true }); nav(`/producto/${id}`) }
    else setMsg({ t: `Imagen recibida pero sigue PENDIENTE (${status}): ${JSON.stringify(body)}. Puedes Reintentar.`, ok: false })
  }
  async function reprocesar() {
    if (!pid) return
    const { status, body } = await api(`/productos/${pid}/reprocesar`, { method: 'POST' })
    setMsg({ t: `Reprocesar ${status}: ${JSON.stringify(body)}`, ok: status === 200 })
  }
  const attrs = ATTR_SETS[form.categoria_id] || []
  return (
    <div style={{ maxWidth: 640 }}>
      <h2>Registrar producto</h2>
      <form onSubmit={submit} style={{ display: 'grid', gap: 8 }}>
        <input placeholder="Codigo unico (ej TEC-001)" value={form.codigo} onChange={e => set('codigo', e.target.value)} required />
        <input placeholder="Nombre" value={form.nombre} onChange={e => set('nombre', e.target.value)} required />
        <textarea placeholder="Descripcion" value={form.descripcion} onChange={e => set('descripcion', e.target.value)} />
        <input placeholder="Precio" type="number" step="0.01" min="0" value={form.precio} onChange={e => set('precio', e.target.value)} required />
        <select value={form.categoria_id} onChange={e => set('categoria_id', e.target.value)}>
          {cats.map(c => <option key={c.categoria_id} value={c.categoria_id}>{c.categoria_id} - {c.nombre}</option>)}
        </select>
        <fieldset><legend>Atributos variables</legend>
          {attrs.map(a => <input key={a.k} placeholder={`${a.label} (${a.ph})`} value={form.atributos[a.k] || ''} onChange={e => setAttr(a.k, e.target.value)} required />)}
        </fieldset>
        <input type="file" accept="image/jpeg,image/png" onChange={e => setFile(e.target.files[0])} />
        <button type="submit">Registrar</button>
        {pid && <button type="button" onClick={reprocesar}>Reintentar / Reprocesar {pid}</button>}
      </form>
      {msg && <p style={{ color: msg.ok === true ? 'green' : msg.ok === false ? 'red' : 'black' }}>{msg.t}</p>}
      {pid && <p>producto_id: <b>{pid}</b></p>}
    </div>
  )
}

function Catalogo() {
  const [data, setData] = useState({ productos: [], total: 0 })
  useEffect(() => { api('/productos').then(({ body }) => setData(body)) }, [])
  return (
    <div>
      <h2>Catalogo ({data.total} publicados)</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 12 }}>
        {(data.productos || []).map(p => (
          <Link key={p.producto_id} to={`/producto/${p.producto_id}`} style={{ border: '1px solid #ccc', padding: 8, textDecoration: 'none', color: 'inherit' }}>
            <img src={imgUrl(p.producto_id)} alt={p.nombre} style={{ width: '100%', height: 140, objectFit: 'cover', background: '#eee' }} />
            <b>{p.nombre}</b><br />{p.categoria} - ${p.precio}<br /><small>{p.codigo}</small>
          </Link>
        ))}
      </div>
    </div>
  )
}

function Detalle() {
  const { id } = useParams()
  const [p, setP] = useState(null)
  useEffect(() => { api(`/productos/${id}`).then(({ body }) => setP(body)) }, [id])
  if (!p) return <p>Cargando...</p>
  return (
    <div>
      <h2>{p.nombre} ({p.estado})</h2>
      <img src={imgUrl(id)} alt={p.nombre} style={{ maxWidth: 400 }} />
      <p><b>Codigo:</b> {p.codigo} | <b>Precio:</b> ${p.precio} | <b>Categoria:</b> {p.categoria}</p>
      <p>{p.descripcion}</p>
      <h4>Atributos</h4>
      <ul>{Object.entries(p.atributos || {}).map(([k, v]) => <li key={k}>{k}: {v}</li>)}</ul>
      <p><small>producto_id: {p.producto_id} | miniatura: {p.miniatura_key} | proc: {p.estado_procesamiento}</small></p>
      <Link to="/">Volver</Link>
    </div>
  )
}

export default function App() {
  return (
    <div style={{ fontFamily: 'sans-serif', padding: 16 }}>
      <h1>Lomax SA - Catalogo</h1>
      <nav style={{ display: 'flex', gap: 12 }}><Link to="/">Catalogo</Link><Link to="/registrar">Registrar</Link></nav>
      <hr />
      <Routes><Route path="/" element={<Catalogo />} /><Route path="/registrar" element={<Registro />} /><Route path="/producto/:id" element={<Detalle />} /></Routes>
    </div>
  )
}

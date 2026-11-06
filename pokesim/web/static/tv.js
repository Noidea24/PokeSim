// TV view: every running adventure on one screen, for a wall display or a small kiosk.
//
// Options, all in the address:
//   ?ids=a,b     only these adventures, in this order
//   ?all=1       include stopped adventures (they show their last numbers)
//   ?stream=0    still frames instead of live video, for a slow kiosk or network.
//                Live video for every game arrives on one connection (/api/v1/tv/stream),
//                because browsers hold only about six open connections to one server and
//                one stream per tile would leave none for sprites and stats.
//   ?fps=30      frames per second: live 1 to 60 (default: the server's STREAM_FPS),
//                stills 0.2 to 10 (default 2)
//   ?info=0      screens only, no name and stats strip
//   ?bare=1      hide the top bar too
(() => {
  const params = new URLSearchParams(location.search)
  const flag = (name) => params.get(name)
  const only = (flag('ids') || '').split(',').map((s) => s.trim()).filter(Boolean)
  const showAll = flag('all') === '1'
  const live = flag('stream') !== '0' && 'ReadableStream' in window && 'createImageBitmap' in window
  const fps = live ? Math.min(60, Math.max(1, Math.round(Number(flag('fps')) || 0))) || 0
    : Math.min(10, Math.max(0.2, Number(flag('fps')) || 2))
  const ACTIVE = new Set(['running', 'paused', 'manual', 'trading'])
  const STATE_LABEL = { paused: 'PAUSED', manual: 'MANUAL', trading: 'TRADING', stopped: 'STOPPED', failed: 'FAILED' }
  const SPRITES = 'rom-portraits-1'
  const grid = document.getElementById('tv-grid')
  const empty = document.getElementById('tv-empty')
  const totals = document.getElementById('tv-totals')
  const tiles = new Map()
  let order = ''
  let pollTimer = null
  let feed = null          // { key, abort } for the live connection

  if (flag('bare') === '1') document.body.classList.add('bare')
  if (flag('info') === '0') document.body.classList.add('no-info')

  const el = (tag, className, text) => {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text !== undefined) node.textContent = text
    return node
  }
  const gameBase = (id) => `/games/${encodeURIComponent(id)}/`

  function cells(count, total) {
    const box = el('span', total > 8 ? 'tv-cells many' : 'tv-cells')
    for (let i = 0; i < total; i++) box.appendChild(el('i', i < count ? 'on' : ''))
    return box
  }

  function meter(label, value, total, withCells) {
    const node = el('span', 'tv-meter')
    node.appendChild(el('span', '', label))
    if (withCells) node.appendChild(cells(Number(value) || 0, total))
    node.appendChild(el('b', '', value == null ? '-' : String(value)))
    if (!withCells && total) node.appendChild(el('span', '', `/${total}`))
    return node
  }

  function build(adventure) {
    const tile = el('a', 'tv-tile')
    tile.href = gameBase(adventure.id)
    const screen = el('div', 'tv-screen')
    const img = el('canvas')
    img.width = 160
    img.height = 144
    img.setAttribute('role', 'img')
    img.setAttribute('aria-label', `${adventure.name} game screen`)
    const state = el('span', 'tv-state')
    state.hidden = true
    screen.append(img, state)
    const info = el('div', 'tv-info')
    const name = el('span', 'tv-name')
    const game = el('span', 'tv-game')
    const where = el('span', 'tv-where')
    const meters = el('div', 'tv-meters')
    const party = el('div', 'tv-party')
    info.append(name, game, where, meters, party)
    tile.append(screen, info)
    return { tile, img, state, name, game, where, meters, party, partyKey: '', active: null,
             pending: null, drawing: false }
  }

  function update(view, a) {
    view.tile.title = `${a.name}, ${a.game}`
    view.name.textContent = a.player ? `${a.name} · ${a.player}` : a.name
    view.game.textContent = `${a.game} ${a.speed === 0 ? 'MAX' : `${a.speed}x`}`
    view.where.textContent = [a.location, a.playtime].filter(Boolean).join(' · ') || 'Waiting for the first report'
    view.meters.replaceChildren(
      meter('BADGES', a.badges, a.badge_total, true),
      meter('DEX', a.owned, a.dex_total, false),
      ...(a.hall_of_fame ? [meter('HOF', a.hall_of_fame, 0, false)] : []))
    const partyKey = JSON.stringify(a.party)
    if (partyKey !== view.partyKey) {
      view.partyKey = partyKey
      view.party.replaceChildren(...(a.party || []).filter((mon) => mon.dex).map((mon) => {
        const sprite = el('img', mon.shiny ? 'shiny' : '')
        sprite.src = `${gameBase(a.id)}sprites/${mon.shiny ? 'shiny/' : ''}${Number(mon.dex)}.png?v=${SPRITES}`
        sprite.alt = ''
        sprite.title = `${mon.nick || mon.species} Lv${mon.level}`
        sprite.loading = 'lazy'
        return sprite
      }))
    }
    const label = STATE_LABEL[a.state]
    view.state.hidden = !label
    view.state.textContent = label || ''
    view.active = ACTIVE.has(a.state)
  }

  // Draw one PNG frame into a tile. If frames arrive faster than they decode, keep only the newest.
  function show(view, blob) {
    if (view.drawing) { view.pending = blob; return }
    view.drawing = true
    createImageBitmap(blob).then((bitmap) => {
      const canvas = view.img
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width
        canvas.height = bitmap.height
      }
      const ctx = canvas.getContext('2d')
      ctx.imageSmoothingEnabled = false
      ctx.drawImage(bitmap, 0, 0)
      bitmap.close?.()
      canvas.classList.add('ready')
    }).catch(() => {}).finally(() => {
      view.drawing = false
      const next = view.pending
      view.pending = null
      if (next) show(view, next)
    })
  }

  function setScreens() {
    for (const view of tiles.values()) if (!view.active) view.img.classList.remove('ready')
    if (live) return openFeed()
    clearInterval(pollTimer)
    pollTimer = setInterval(pollFrames, 1000 / fps)
    pollFrames()
  }

  // One connection carries every live game: "<id> <length>\n" then that many PNG bytes.
  function openFeed() {
    const ids = [...tiles].filter(([, view]) => view.active).map(([id]) => id)
    const key = ids.join(',')
    if (feed && feed.key === key && !feed.ended) return
    feed?.abort.abort()
    feed = null
    if (!ids.length) return
    const abort = new AbortController()
    const current = { key, abort, ended: false }
    feed = current
    const query = new URLSearchParams({ ids: key })
    if (fps) query.set('fps', String(fps))
    readFeed(`/api/v1/tv/stream?${query}`, abort.signal)
      .catch(() => {})
      .finally(() => { current.ended = true })
  }

  async function readFeed(url, signal) {
    const response = await fetch(url, { cache: 'no-store', signal })
    if (!response.ok || !response.body) return
    const reader = response.body.getReader()
    let buffer = new Uint8Array(0)
    for (;;) {
      const { value, done } = await reader.read()
      if (done) return
      const joined = new Uint8Array(buffer.length + value.length)
      joined.set(buffer)
      joined.set(value, buffer.length)
      buffer = joined
      for (;;) {
        const newline = buffer.indexOf(10)
        if (newline < 0) break
        const [id, size] = new TextDecoder().decode(buffer.subarray(0, newline)).split(' ')
        const length = Number(size)
        if (!id || !Number.isFinite(length)) return
        if (buffer.length < newline + 1 + length) break
        const frame = buffer.slice(newline + 1, newline + 1 + length)
        buffer = buffer.slice(newline + 1 + length)
        const view = tiles.get(id)
        if (view && view.active && !document.hidden) show(view, new Blob([frame], { type: 'image/png' }))
      }
    }
  }

  // Fetch the next still and draw it once it has arrived, so a slow frame never blanks the tile.
  function pollFrames() {
    if (document.hidden) return
    for (const [id, view] of tiles) {
      if (!view.active || view.loading) continue
      view.loading = true
      fetch(`${gameBase(id)}frame.jpg?t=${Date.now()}`, { cache: 'no-store' })
        .then((response) => (response.ok ? response.blob() : null))
        .then((blob) => { if (blob) show(view, blob) })
        .catch(() => {})
        .finally(() => { view.loading = false })
    }
  }

  // Pick the column count that gives every Game Boy screen the most room.
  function layout() {
    const count = tiles.size
    if (!count) return
    const style = getComputedStyle(grid)
    const gap = parseFloat(style.rowGap) || 8
    const width = grid.clientWidth - gap * 2
    const height = grid.clientHeight - gap * 2
    const sample = tiles.values().next().value
    const strip = document.body.classList.contains('no-info') ? 0 : (sample.tile.querySelector('.tv-info')?.offsetHeight || 0)
    let best = { cols: 1, size: 0 }
    for (let cols = 1; cols <= count; cols++) {
      const rows = Math.ceil(count / cols)
      const tileWidth = (width - gap * (cols - 1)) / cols
      const screenHeight = (height - gap * (rows - 1)) / rows - strip
      const size = Math.min(tileWidth, screenHeight * 10 / 9)
      if (size > best.size) best = { cols, size }
    }
    // Size tiles to the screen they hold, so a wide display shows black bars around the grid,
    // not inside every tile.
    grid.style.setProperty('--tv-cols', best.cols)
    grid.style.setProperty('--tv-width', `${Math.floor(best.size)}px`)
    grid.style.setProperty('--tv-height', `${Math.floor(best.size * 9 / 10 + strip)}px`)
  }

  function render(data) {
    const list = (data.list || [])
      .filter((a) => (only.length ? only.includes(a.id) : showAll || ACTIVE.has(a.state)))
      .sort((a, b) => (only.length ? only.indexOf(a.id) - only.indexOf(b.id) : 0))
    const key = list.map((a) => a.id).join(',')
    if (key !== order) {
      order = key
      for (const id of [...tiles.keys()]) if (!list.some((a) => a.id === id)) tiles.delete(id)
      for (const a of list) if (!tiles.has(a.id)) tiles.set(a.id, build(a))
      grid.replaceChildren(...list.map((a) => tiles.get(a.id).tile))
    }
    list.forEach((a) => update(tiles.get(a.id), a))
    setScreens()
    empty.hidden = list.length > 0
    grid.hidden = list.length === 0
    const hours = Math.floor((data.playtime_seconds || 0) / 3600)
    totals.textContent = `${data.running} running · ${data.badges} badges · ${data.owned} caught · ${hours} h played`
    requestAnimationFrame(layout)
  }

  async function refresh() {
    try {
      const response = await fetch('/api/v1/stats', { cache: 'no-store' })
      if (response.ok) render(await response.json())
    } catch (_) { /* Keep the last picture while the library restarts. */ }
  }

  addEventListener('resize', layout)
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh() })
  document.getElementById('tv-full').addEventListener('click', () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else document.documentElement.requestFullscreen?.()
  })
  let idle = null
  const wake = () => {
    document.body.classList.remove('idle')
    clearTimeout(idle)
    idle = setTimeout(() => document.body.classList.add('idle'), 3000)
  }
  addEventListener('pointermove', wake)
  wake()
  refresh()
  setInterval(refresh, 5000)
})()

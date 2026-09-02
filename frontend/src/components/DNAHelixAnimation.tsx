import { useEffect, useRef, useState } from 'react'

/**
 * DNAHelixAnimation - a decorative double helix for the analysis states.
 *
 * The component owns no workflow logic and no status of its own: it is driven
 * entirely by the caller's existing loading flag (`active`), so it can never
 * invent progress. It turns while a real request is in flight and plays a short
 * settle-and-fade exit when that request resolves. The verification result stays
 * rendered by the surrounding components, untouched.
 *
 * Why a canvas plus a requestAnimationFrame loop:
 *   - Depth ordering and depth shading of ~190 shapes per frame is not reachable
 *     with CSS transforms over static markup, and 190 DOM nodes would be far
 *     more expensive than one canvas.
 *   - Rotation around the vertical axis is done the exact way: a helix is
 *     invariant under (rotate about its axis, translate along its axis) applied
 *     together, so advancing the phase of `sin(theta)` with height *is* a
 *     uniform rotation - no projection matrices, no third-party renderer.
 *   - The loop lives outside React, so frames never cause a re-render, and the
 *     frame itself allocates nothing: the geometry is written into a pair of
 *     pre-allocated point arrays and the shapes into a reusable primitive pool.
 *
 * Housekeeping rules honoured here:
 *   - Nothing is added to the global stylesheet; no new dependency; no new
 *     colour - every value mirrors an existing `@theme` token from index.css
 *     (brand-200..700) or the brand wash already painted on body.
 *   - Drawing pauses when the element leaves the viewport or the tab is hidden.
 *   - `prefers-reduced-motion` renders one static, fully formed frame and skips
 *     the particles, travellers, breathing and settle sweep.
 *   - The loop, the interval-free timers, both observers and the media-query
 *     listener are released on unmount.
 *
 * Sizing: the caller controls the box through `className` (e.g. `h-44 w-full`).
 * The helix scales itself to whatever box it is given and never overflows it.
 */

/** brand-200 .. brand-700 from the existing theme - nothing outside it. */
const BRAND = {
  deep: '#047857', // brand-700
  mid: '#059669', // brand-600
  core: '#10b981', // brand-500
  light: '#34d399', // brand-400
  pale: '#6ee7b7', // brand-300
  faint: '#a7f3d0', // brand-200
} as const

// The two backbones are tinted with different halves of the same green ramp
// (brand-300..500 against brand-500..700) so the eye reads "two strands wound
// around one axis" instead of "one coiled wire". Within each strand the ramp is
// applied by depth: bright on the near side, dark as it passes behind.
const STRANDS = [
  { far: BRAND.core, mid: BRAND.light, near: BRAND.pale }, // brand-500/400/300
  { far: BRAND.deep, mid: BRAND.mid, near: BRAND.core }, // brand-700/600/500
] as const

type Rgb = readonly [number, number, number]

const toRgb = (hex: string): Rgb => [
  Number.parseInt(hex.slice(1, 3), 16),
  Number.parseInt(hex.slice(3, 5), 16),
  Number.parseInt(hex.slice(5, 7), 16),
]

const mix = (from: Rgb, to: Rgb, t: number): string =>
  `rgb(${Math.round(from[0] + (to[0] - from[0]) * t)}, ${Math.round(
    from[1] + (to[1] - from[1]) * t,
  )}, ${Math.round(from[2] + (to[2] - from[2]) * t)})`

/**
 * Each backbone gets a continuous depth ramp rather than three flat bands: hard
 * band edges are what make a segmented curve read as a string of beads.
 * Pre-computed once, so `shade()` stays allocation-free at 60 fps.
 */
const RAMP_STEPS = 24
const RAMPS: string[][] = STRANDS.map(({ far, mid, near }) => {
  const [f, m, n] = [toRgb(far), toRgb(mid), toRgb(near)]
  return Array.from({ length: RAMP_STEPS + 1 }, (_, i) => {
    const t = i / RAMP_STEPS
    return t < 0.5 ? mix(f, m, t * 2) : mix(m, n, (t - 0.5) * 2)
  })
})

/** The brand-500 rgb triple already used by the body wash and gv focus rings. */
const GLOW = 'rgba(16, 185, 129,'

const TURNS = 1.7 // visible turns: enough to read the pitch without crowding a card
const SAMPLES = 72 // segments per backbone - fine enough that the curve stays smooth
const RUNG_EVERY = 8 // one base pair every N samples - sparse enough to stay legible
const PARTICLES = 12 // deliberately few; they must not dominate the panel
const TRAVELLERS = 2 // one energy point per backbone

const ROTATION_SECONDS = 9 // one revolution: slow, continuous, never twitchy
const BREATHE_SECONDS = 7 // vertical float period
const BREATHE_PX = 3 // ... and its deliberately small amplitude
const WAVE_SECONDS = 4.5 // base-pair illumination sweep period
const SETTLE_MS = 1100 // completion: slow down, stabilise, pulse
const FADE_MS = 320 // exit fade, same length as --animate-gv-fade-in
const EASE = 'cubic-bezier(0.16, 1, 0.3, 1)' // --ease-gv

const TWO_PI = Math.PI * 2

/** Base pairs per frame: indices 1, 1 + N, 1 + 2N ... below SAMPLES. */
const RUNGS = Math.ceil((SAMPLES - 1) / RUNG_EVERY)

/**
 * Upper bound of what one frame can need, derived from the constants above so it
 * cannot drift out of sync with the loops that fill it: 144 backbone segments,
 * then per base pair two half-rungs, two attach nodes and at most one
 * illumination dot, plus the travellers and particles.
 */
const PRIMITIVES = 2 * SAMPLES + 5 * RUNGS + TRAVELLERS + PARTICLES

type Kind = 'line' | 'rung' | 'orb'

/** A point on a backbone, in canvas space, with its 0..1 depth (1 = nearest). */
type Point = { x: number; y: number; depth: number }

interface Primitive {
  kind: Kind
  depth: number // painter's algorithm key: 0 = far side, 1 = near side
  x1: number
  y1: number
  x2: number
  y2: number
  size: number // line width, or radius for an orb
  alpha: number
  color: string
  glow: number // shadow blur in px for the accent glow, 0 = no glow
}

type Presentation = 'hidden' | 'visible' | 'settling' | 'exiting'

const easeOutCubic = (t: number): number => 1 - (1 - t) ** 3

const prefersReducedMotion = (): boolean =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

export default function DNAHelixAnimation({
  active,
  className = '',
}: {
  active: boolean
  className?: string
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [presentation, setPresentation] = useState<Presentation>('hidden')
  const [entered, setEntered] = useState(false)

  // Set by the renderer while it is mounted. A new run that starts during the
  // settle/exit has to re-arm the loop, which otherwise stopped itself.
  const restartRef = useRef<(() => void) | null>(null)

  // Written by the state machine, read by the animation loop. 0 = still running,
  // > 0 = timestamp where the completion settle began.
  const settleAtRef = useRef(0)

  // --- State machine -------------------------------------------------------
  // `hidden` costs nothing at all: no element, no loop, no observers.

  useEffect(() => {
    if (active) {
      setPresentation('visible')
      restartRef.current?.()
      return
    }
    // Only something that was actually showing has an exit to play. The exit is
    // decoration on its way out, not a claim about work still running: the
    // result is already on screen underneath it, nothing is awaited or delayed.
    setPresentation((previous) => (previous === 'visible' ? 'settling' : previous))
  }, [active])

  useEffect(() => {
    if (presentation === 'visible') settleAtRef.current = 0
    if (presentation === 'settling') settleAtRef.current = performance.now()
  }, [presentation])

  useEffect(() => {
    if (presentation !== 'settling' && presentation !== 'exiting') return
    // Under reduced motion there is no sweep to wait for: move on straight away.
    const delay = presentation === 'settling' ? (prefersReducedMotion() ? 0 : SETTLE_MS) : FADE_MS
    const timer = window.setTimeout(
      () => setPresentation(presentation === 'settling' ? 'exiting' : 'hidden'),
      delay,
    )
    return () => window.clearTimeout(timer)
  }, [presentation])

  // Entrance: one painted frame at opacity 0, then the transition takes over.
  useEffect(() => {
    if (presentation === 'hidden') {
      setEntered(false)
      return
    }
    if (entered) return
    const id = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(id)
  }, [presentation, entered])

  // --- Renderer ------------------------------------------------------------
  // Keyed on "shown at all" rather than on the presentation step, so the loop
  // survives visible -> settling -> exiting with its rotation phase intact and
  // the helix never snaps back to frame 0.
  const shown = presentation !== 'hidden'

  useEffect(() => {
    if (!shown) return
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    if (!wrap || !canvas) return

    const context = canvas.getContext('2d')
    if (!context) return // a browser without 2D canvas simply shows nothing

    const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    const state = {
      phase: 0,
      lastFrame: 0,
      pulse: -1,
      width: 0,
      height: 0,
      cx: 0,
      scale: 1,
      wavelength: 1,
      amplitude: 1,
      breathe: 0,
      haze: null as CanvasGradient | null,
    }

    // Reused every frame: a helix frame is ~190 shapes plus two polylines, and
    // allocating them 60 times a second is pure garbage pressure.
    const pool: Primitive[] = Array.from({ length: PRIMITIVES }, () => ({
      kind: 'line' as Kind,
      depth: 0,
      x1: 0,
      y1: 0,
      x2: 0,
      y2: 0,
      size: 0,
      alpha: 0,
      color: '',
      glow: 0,
    }))
    const order: Primitive[] = []
    let count = 0

    const next = (): Primitive => {
      const primitive = pool[count]
      count += 1
      primitive.glow = 0
      return primitive
    }

    /** Both backbones, sampled once per frame and read by every loop below. */
    const backbone: Point[][] = [0, 1].map(() =>
      Array.from({ length: SAMPLES + 1 }, () => ({ x: 0, y: 0, depth: 0 })),
    )

    /**
     * Rotation around the vertical axis, done exactly. Strand 1 is strand 0
     * offset by half a turn, which also makes its depth the complement of
     * strand 0's - so one end of every base pair is always near, the other far.
     */
    const computeBackbone = () => {
      for (let strand = 0; strand < 2; strand += 1) {
        const points = backbone[strand]
        for (let index = 0; index <= SAMPLES; index += 1) {
          const y = (index / SAMPLES) * state.height + state.breathe
          const theta = ((y + state.phase) / state.wavelength) * TWO_PI + strand * Math.PI
          const point = points[index]
          point.x = state.cx + Math.sin(theta) * state.amplitude
          point.y = y
          point.depth = (Math.cos(theta) + 1) / 2
        }
      }
    }

    /** Depth shading inside one backbone: bright on the near side, dark behind. */
    const shade = (strand: number, depth: number): string =>
      RAMPS[strand][Math.round(Math.max(0, Math.min(1, depth)) * RAMP_STEPS)]

    /** Dissolve into the card edge instead of being clipped by it. */
    const endFade = (y: number): number => {
      const edge = Math.min(y, state.height - y) / (state.height * 0.12)
      return Math.max(0.22, Math.min(1, edge))
    }

    /**
     * One half of a base pair, from a backbone to the axis. Its depth is taken
     * halfway between that backbone and the middle of the helix, so the near
     * half paints after the far backbone and before the near one, as it truly
     * does in three dimensions.
     */
    const halfRung = (from: Point, to: Point, strand: number, lit: number) => {
      const rung = next()
      rung.kind = 'rung'
      rung.depth = (from.depth + 0.5) / 2
      rung.x1 = from.x
      rung.y1 = from.y
      rung.x2 = (from.x + to.x) / 2
      rung.y2 = (from.y + to.y) / 2
      rung.color = shade(strand, from.depth)
      rung.size = (1.3 + 1.2 * from.depth + lit * 0.4) * state.scale
      rung.alpha = (0.34 + 0.34 * from.depth + lit * 0.3) * endFade(from.y)
    }

    /** The node where a base pair meets a backbone. */
    const attachNode = (point: Point, strand: number, lit: number) => {
      const orb = next()
      orb.kind = 'orb'
      orb.depth = Math.min(1, point.depth + 0.02)
      orb.x1 = point.x
      orb.y1 = point.y
      orb.size = (0.9 + 0.9 * point.depth) * state.scale
      orb.color = shade(strand, point.depth)
      orb.alpha = (0.16 + 0.46 * point.depth + lit * 0.12) * endFade(point.y)
      orb.glow =
        (point.depth > 0.62 || lit > 0.5) && !motionQuery.matches ? 6 * state.scale : 0
    }

    const paint = (time: number) => {
      const { width, height, scale } = state
      if (width < 2 || height < 2) return

      const reduced = motionQuery.matches
      state.breathe =
        reduced ? 0 : Math.sin((time / 1000 / BREATHE_SECONDS) * TWO_PI) * BREATHE_PX
      const settling = state.pulse >= 0
      const progress = settling ? state.pulse : 0
      // Where the illumination crest sits along the axis, 0..1, travelling upward.
      const wave = reduced || settling ? -1 : (time / 1000 / WAVE_SECONDS) % 1

      count = 0
      context.clearRect(0, 0, width, height)
      context.lineCap = 'round'
      // A breath of accent haze behind the column: it is what carries the "glow"
      // requirement, and it stops a narrow helix from looking lost in a wide card.
      // It never moves, so it stays put under reduced motion as well.
      if (state.haze) {
        context.fillStyle = state.haze
        context.fillRect(0, 0, width, height)
      }
      computeBackbone()

      // Backbones.
      for (let strand = 0; strand < 2; strand += 1) {
        const points = backbone[strand]
        for (let index = 0; index < SAMPLES; index += 1) {
          const from = points[index]
          const to = points[index + 1]
          const depth = (from.depth + to.depth) / 2
          const segment = next()
          segment.kind = 'line'
          segment.depth = depth
          segment.x1 = from.x
          segment.y1 = from.y
          segment.x2 = to.x
          segment.y2 = to.y
          segment.color = shade(strand, depth)
          segment.size = (1.6 + 2.4 * depth) * scale
          segment.alpha = (0.42 + 0.5 * depth) * endFade(from.y)
        }
      }

      // Base pairs, with a crest of illumination travelling along the axis.
      for (let index = 1; index < SAMPLES; index += RUNG_EVERY) {
        const a = backbone[0][index]
        const b = backbone[1][index]
        let lit = 0
        if (settling) {
          lit = Math.min(1, progress * 2) // stabilise: the whole ladder holds one steady glow
        } else if (wave >= 0) {
          const rel = ((((a.y - state.breathe) / height - wave) % 1) + 1) % 1
          lit = Math.max(0, 1 - Math.min(rel, 1 - rel) * 7)
        }
        halfRung(a, b, 0, lit)
        halfRung(b, a, 1, lit)
        // Beads only where the base pair meets the near backbone: on the far
        // side they would break the strand up into a string of dots.
        if (a.depth > 0.42) attachNode(a, 0, lit)
        if (b.depth > 0.42) attachNode(b, 1, lit)
        if (lit > 0.25) {
          // The crest reads as base-pair illumination, not as an extra speckle.
          const dot = next()
          dot.kind = 'orb'
          dot.depth = 0.5
          dot.x1 = (a.x + b.x) / 2
          dot.y1 = (a.y + b.y) / 2
          dot.size = 1.5 * scale
          dot.color = BRAND.pale
          dot.alpha = lit * 0.8
          dot.glow = 8 * scale
        }
      }

      if (!reduced) {
        // Two travelling data points, one per backbone.
        for (let strand = 0; strand < TRAVELLERS; strand += 1) {
          const index = (((time / 26) + strand * (SAMPLES / TRAVELLERS)) % SAMPLES) | 0
          const point = backbone[strand][index]
          const orb = next()
          orb.kind = 'orb'
          orb.depth = Math.min(1, point.depth + 0.05)
          orb.x1 = point.x
          orb.y1 = point.y
          orb.size = 2.4 * scale
          orb.color = BRAND.faint
          orb.alpha = 0.55 + 0.45 * point.depth
          orb.glow = 12 * scale
        }

        // A handful of drifting particles. They use the box width rather than the
        // helix amplitude, so a wide panel reads as "field" instead of "two empty
        // margins around a stick", while staying inside the canvas.
        const spread = Math.min(width * 0.42, state.amplitude * 3.2)
        for (let i = 0; i < PARTICLES; i += 1) {
          const seed = i * 1.37
          const drift = (time / 1000) * (0.1 + (i % 3) * 0.04) + seed
          const depth = (Math.sin(drift + seed) + 1) / 2
          const orb = next()
          orb.kind = 'orb'
          orb.depth = depth * 0.8
          orb.x1 = state.cx + Math.sin(drift * 1.7 + seed) * spread
          orb.y1 = ((((drift * 0.09 + seed * 0.13) % 1) + 1) % 1) * height
          orb.size = (0.8 + 0.9 * depth) * scale
          orb.color = depth > 0.5 ? BRAND.pale : BRAND.faint
          orb.alpha = (0.16 + 0.26 * depth) * endFade(orb.y1)
        }
      }

      // Painter's algorithm: far side first, so the helix crosses itself correctly.
      order.length = count
      for (let i = 0; i < count; i += 1) order[i] = pool[i]
      order.sort((a, b) => a.depth - b.depth)

      for (const shape of order) {
        context.globalAlpha = shape.alpha
        if (shape.kind === 'line' || shape.kind === 'rung') {
          context.strokeStyle = shape.color
          context.lineWidth = shape.size
          context.beginPath()
          context.moveTo(shape.x1, shape.y1)
          context.lineTo(shape.x2, shape.y2)
          context.stroke()
        } else {
          if (shape.glow) {
            context.shadowColor = `${GLOW} 0.45)`
            context.shadowBlur = shape.glow
          }
          context.fillStyle = shape.color
          context.beginPath()
          context.arc(shape.x1, shape.y1, shape.size, 0, TWO_PI)
          context.fill()
          context.shadowBlur = 0
        }
      }
      context.globalAlpha = 1

      // Completion: one soft ring that expands once and dissolves, then everything
      // fades. Timed to the settle, so it never outstays the result appearing.
      if (settling && progress > 0.25) {
        const p = (progress - 0.25) / 0.75
        context.globalAlpha = (1 - p) * 0.45
        context.strokeStyle = BRAND.core
        context.lineWidth = 2.2 * scale * (1 - p * 0.7)
        context.beginPath()
        context.arc(
          state.cx,
          height / 2,
          Math.max(1, easeOutCubic(p) * Math.min(width, height) * 0.55),
          0,
          TWO_PI,
        )
        context.stroke()
        context.globalAlpha = 1
      }
    }

    let frame = 0
    let onScreen = true

    /**
     * Geometry for the current box. Stroke weights and node radii are keyed to
     * the height rather than to the box diagonal, because the helix is a tall
     * narrow figure and it is the caller's height that sets how dense it reads.
     */
    const layout = () => {
      state.cx = state.width / 2
      state.scale = Math.max(0.4, Math.min(state.height / 180, state.width / 150))
      state.wavelength = state.height / TURNS
      state.amplitude = Math.min(state.width * 0.34, state.height * 0.36)
      const haze = context.createRadialGradient(
        state.cx,
        state.height / 2,
        0,
        state.cx,
        state.height / 2,
        Math.max(state.amplitude * 2.4, state.height * 0.5),
      )
      // brand-500 at 7% -> transparent: the same wash strength as body's radial.
      haze.addColorStop(0, `${GLOW} 0.07)`)
      haze.addColorStop(0.6, `${GLOW} 0.03)`)
      haze.addColorStop(1, `${GLOW} 0)`)
      state.haze = haze
    }

    const sizeCanvas = () => {
      const box = wrap.getBoundingClientRect()
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      state.width = Math.max(0, Math.round(box.width))
      state.height = Math.max(0, Math.round(box.height))
      canvas.width = Math.round(state.width * dpr)
      canvas.height = Math.round(state.height * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
      layout()
      paint(performance.now())
    }

    const tick = (now: number) => {
      frame = requestAnimationFrame(tick)
      if (!onScreen || document.hidden) {
        state.lastFrame = now // resume smoothly instead of jumping ahead
        return
      }
      const delta = state.lastFrame ? Math.min((now - state.lastFrame) / 1000, 0.05) : 0
      state.lastFrame = now

      const wavelength = state.wavelength
      const settleStart = settleAtRef.current
      if (settleStart) {
        // Ease the rotation out to a standstill; no jump, no restart.
        const progress = Math.min(1, (now - settleStart) / SETTLE_MS)
        state.pulse = progress
        state.phase += (wavelength / ROTATION_SECONDS) * delta * (1 - easeOutCubic(progress))
        state.phase %= wavelength
        paint(now)
        if (progress >= 1) stop() // hold the finished frame; the fade owns the rest
        return
      }
      state.pulse = -1
      state.phase += (wavelength / ROTATION_SECONDS) * delta
      state.phase %= wavelength
      paint(now)
    }

    const start = () => {
      if (frame || motionQuery.matches) return
      state.lastFrame = 0
      frame = requestAnimationFrame(tick)
    }
    const stop = () => {
      if (!frame) return
      cancelAnimationFrame(frame)
      frame = 0
    }

    const resize = new ResizeObserver(sizeCanvas)
    resize.observe(wrap)

    const visibility = new IntersectionObserver((entries) => {
      onScreen = entries.some((entry) => entry.isIntersecting)
      if (onScreen) start()
      else stop()
    })
    visibility.observe(wrap)

    const onMotionChange = () => {
      stop()
      sizeCanvas() // reduced motion: one static, fully formed frame
      if (!motionQuery.matches) start() // motion allowed again: carry on turning
    }
    motionQuery.addEventListener('change', onMotionChange)

    sizeCanvas()
    restartRef.current = start
    if (motionQuery.matches) paint(performance.now())
    else start()

    return () => {
      stop()
      restartRef.current = null
      resize.disconnect()
      visibility.disconnect()
      motionQuery.removeEventListener('change', onMotionChange)
      settleAtRef.current = 0
    }
  }, [shown])

  if (presentation === 'hidden') return null

  return (
    // The grid row is what collapses, so the exiting helix takes its space away
    // with it instead of snapping the result underneath it.
    <div
      className="grid overflow-hidden transition-[grid-template-rows]"
      style={{
        gridTemplateRows: presentation === 'exiting' ? '0fr' : '1fr',
        transitionDuration: `${FADE_MS}ms`,
        transitionTimingFunction: EASE,
      }}
    >
      <div
        ref={wrapRef}
        aria-hidden="true"
        className={`pointer-events-none min-h-0 select-none transition-opacity ${className}`}
        style={{
          opacity: entered && presentation !== 'exiting' ? 1 : 0,
          transitionDuration: `${FADE_MS}ms`,
          transitionTimingFunction: EASE,
        }}
      >
        <canvas ref={canvasRef} className="block h-full w-full" />
      </div>
    </div>
  )
}

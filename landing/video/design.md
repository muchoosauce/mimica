# Mimica Brand DNA — Video Composition

## Palette

- Canvas (background) : `#0A0A0F`
- Primary violet : `#7C5CFF`
- Secondary pink : `#EC4899`
- Off-white (text/elements) : `#F4F4F6`
- Muted gray : `#9999A0`
- Dim gray : `#5C5C66`
- Card surfaces (dark variant) : `#13131C`
- Borders subtle : `rgba(255, 255, 255, 0.08)`
- Borders emphasized : `rgba(255, 255, 255, 0.14)`

## Gradient

- Primary brand gradient : `linear-gradient(135deg, #7C5CFF 0%, #EC4899 100%)`
- Used on : ad card surfaces, halos, central document accents, scene-specific ink flows
- Gray placeholder (for "competitor" / pre-transformation) : `#3A3A42`

## Typography

- Family : Inter (only used for the orbital "Aa" element, no other text on the animation)
- Weights : Regular 400, SemiBold 600

## Corners

- Cards : 12px
- Pills : 9999px (fully rounded)

## Depth

- Subtle glow halos around key elements (brief icon, winner card)
- No heavy shadows
- Soft radial gradients for ambient depth

## Motion

- Easing standard : `cubic-bezier(0.16, 1, 0.3, 1)` (ease-out-expo)
- Pulse cycle : 2 seconds, scale 1.0 → 1.05 → 1.0
- Orbital rotation : 20 seconds full rotation, linear
- Card materialization : 0.5-0.8 seconds
- Crossfades between services : 0.5-1 second overlap

## Do

- Keep the violet→pink gradient as the signature brand colour
- Keep dark canvas as constant background
- Use subtle haloes for depth
- Maintain the central brief icon visible throughout all 20 seconds

## Don't

- Add captions or text overlays (this composition is silent and purely visual)
- Use heavy drop-shadows
- Introduce colours outside the palette
- Animate abrupt cuts — every scene change must crossfade

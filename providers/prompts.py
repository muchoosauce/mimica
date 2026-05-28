"""System prompts and prompt-generation helpers shared by CLI and GUI."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .parsing import coerce_text, fallback_split, parse_prompts

if TYPE_CHECKING:
    from .base import Provider


# ─── Animation style presets ──────────────────────────────────────────────
#
# A style is injected at the anchor (shot 1) image generation by passing
# `style_ref` as the FIRST image_url to NanoBanana and prefixing `prompt`
# to the LLM instruction. Subsequent shots inherit the style automatically
# through the anchor — they only need the `prompt` prefix as reinforcement.
#
# `style_ref` is a relative path under gui/assets/ resolved at use time so
# the same dict works from CLI, frozen .app bundle, and source-mode runs.

ANIMATION_STYLES: dict[str, dict] = {
    "realistic": {
        "label": "Realistic",
        "prompt": "",
        "style_ref": "",
    },
    "pixar": {
        "label": "Pixar",
        "prompt": (
            "Pixar-style 3D animated render: subtly stylized human "
            "proportions with slightly enlarged eyes, smooth subsurface-"
            "scattered skin with soft specular highlights, hyperreal but "
            "stylized clothing fabric, warm cinematic lighting with rich "
            "color grading, painterly background blur, expressive emotive "
            "face — 3D render quality, not photoreal."
        ),
        "style_ref": "styles/pixar.jpg",
    },
    "claymation": {
        "label": "Claymation",
        "prompt": (
            "Stop-motion claymation still: hand-sculpted clay figure with "
            "visible fingerprint indents and tool marks, glossy plasticine "
            "skin with slight imperfections, hair and fabric sculpted from "
            "clay in stylized shapes, slightly oversized features, diorama-"
            "scale tabletop set, soft directional studio lighting suggesting "
            "the stop-motion rig, shallow depth of field at miniature scale."
        ),
        "style_ref": "styles/claymation.jpg",
    },
    "felt_stop_motion": {
        "label": "Felt stop motion",
        "prompt": (
            "Felt stop-motion still: every surface is hand-cut felted wool "
            "in solid pastel colors, visible stitched seams and fuzzy fiber "
            "texture, slightly squashed proportions like a children's-book "
            "puppet, the entire set is a fabric diorama on a tabletop, soft "
            "warm studio lights, gentle macro depth of field, no glossy or "
            "plastic surfaces — everything is matte felted fabric."
        ),
        "style_ref": "styles/felt_stop_motion.jpg",
    },
    "plush_toy": {
        "label": "Plush toy",
        "prompt": (
            "Plush-toy diorama still: the character is a stuffed plush "
            "doll with soft fuzzy fabric body, embroidered facial features "
            "in thread, button eyes, slightly chunky cute proportions, "
            "visible seams and fabric grain, the room and props rendered "
            "as a child's bedroom playset, warm bedroom lighting, macro "
            "tabletop scale, photoreal fabric textures."
        ),
        "style_ref": "styles/plush_toy.jpg",
    },
    "marionette": {
        "label": "Marionette",
        "prompt": (
            "String-marionette puppet still: wooden carved figure with "
            "visible joints, painted wooden face, fabric clothes draped on "
            "an articulated wooden body, fine strings rising from the head "
            "and limbs to an out-of-frame control bar, sat or posed in a "
            "miniature stage-like set, theatrical warm spotlight, tabletop "
            "diorama scale, painted wood grain visible."
        ),
        "style_ref": "styles/marionette.jpg",
    },
    "animatronic": {
        "label": "Animatronic",
        "prompt": (
            "Animatronic figure still: highly detailed silicone-skinned "
            "humanoid mannequin with visible micro-seams, slightly waxy "
            "complexion suggesting a Disney-park or museum animatronic, "
            "glass eyes with realistic reflections, real fabric clothing, "
            "scene lit like a themed attraction with warm tungsten key "
            "light, photoreal but uncanny — the figure reads as a "
            "lifelike but inanimate animatronic rather than a real human."
        ),
        "style_ref": "styles/animatronic.jpg",
    },
    "plastic_doll": {
        "label": "Plastic doll",
        "prompt": (
            "Fashion-doll still: hyper-glossy injection-molded plastic "
            "figure with smooth featureless joints, painted-on facial "
            "features, exaggerated proportions, plastic-rooted hair with "
            "visible plug pattern, real miniature clothes on a doll body, "
            "diorama-scale dollhouse set, soft studio key light, plastic "
            "specular highlights, tabletop macro scale."
        ),
        "style_ref": "styles/plastic_doll.jpg",
    },
    "action_figure": {
        "label": "Action Figure",
        "prompt": (
            "Premium action-figure still: matte painted PVC plastic "
            "figure with visible articulation joints at the shoulders, "
            "elbows, hips and knees, sculpted hair and clothing, detailed "
            "facial paint app, mannequin-like body posed in a miniature "
            "vignette, dramatic key + rim lighting like a collector toy "
            "photograph, macro lens, shallow depth of field."
        ),
        "style_ref": "styles/action_figure.jpg",
    },
    "wooden_doll": {
        "label": "Wooden doll",
        "prompt": (
            "Carved wooden doll still: figure carved from a single block "
            "of light maple or pine, visible wood grain on every surface, "
            "painted facial features in matte acrylic, simple peg-style "
            "limbs, smooth sanded curves, props and furniture also made of "
            "stained wood, soft window light, craft-fair tabletop diorama "
            "scale, no plastic or metal anywhere."
        ),
        "style_ref": "styles/wooden_doll.jpg",
    },
    "paper_cutout": {
        "label": "Paper cutout",
        "prompt": (
            "Paper-cutout collage still: every element is a flat hand-cut "
            "piece of textured cardstock layered in shallow z-depth, visible "
            "paper grain and cut edges with tiny shadows underneath, limited "
            "color palette of solid pastel sheets, no photoreal shading — "
            "everything reads as construction-paper craft, soft top-down "
            "lighting, slight macro depth of field at tabletop scale."
        ),
        "style_ref": "styles/paper_cutout.jpg",
    },
    "cardboard": {
        "label": "Cardboard",
        "prompt": (
            "Cardboard-craft still: the entire scene including the "
            "character is constructed from corrugated cardboard with "
            "visible fluted edges, brown and tan tones, hand-drawn marker "
            "details for facial features, hot-glue seams visible at "
            "joints, taped joints, slightly imperfect cuts — a school-"
            "project diorama aesthetic, soft daylight, tabletop scale."
        ),
        "style_ref": "styles/cardboard.jpg",
    },
    "lego": {
        "label": "Lego",
        "prompt": (
            "Official Lego minifigure scene: the character is a Lego "
            "minifig with a yellow cylindrical head, painted facial "
            "features, ABS plastic textured body and limbs with the "
            "iconic stud-and-tube connectors, every prop and surface "
            "built from authentic Lego bricks at minifig scale, plastic "
            "micro-roughness on every brick, set lit like a tabletop "
            "Lego photograph, macro lens with shallow depth of field."
        ),
        "style_ref": "styles/lego.jpg",
    },
    "miniature": {
        "label": "Miniature model",
        "prompt": (
            "Tilt-shift miniature model still: a hyperrealistic 1:24 "
            "scale model railway / architectural diorama, real materials "
            "(wood, plaster, fabric) at miniature scale, photoreal but "
            "the tilt-shift compression and extreme shallow depth of "
            "field reveals the model nature, warm key light + cool fill, "
            "tabletop macro photography aesthetic."
        ),
        "style_ref": "styles/miniature.jpg",
    },
    "diorama": {
        "label": "Diorama",
        "prompt": (
            "Hand-built diorama inside a wooden shadow-box: the scene is "
            "framed by visible wooden walls and a glass front, hand-"
            "painted backdrop, mixed-material miniature props (real wood, "
            "fabric, paper, polymer clay), warm interior LED lighting "
            "from inside the box, macro lens shooting into the box, tabletop "
            "craft aesthetic — the viewer is clearly looking at a contained "
            "model scene, not a real environment."
        ),
        "style_ref": "styles/diorama.jpg",
    },
    "porcelain_doll": {
        "label": "Porcelain doll",
        "prompt": (
            "Antique porcelain-doll still: pale glossy porcelain face with "
            "painted blush and lips, glass eyes with realistic catchlights, "
            "rooted mohair wig, period costume in real fabric, slightly "
            "fragile vintage feel, soft warm window light, macro lens, "
            "shallow depth of field — the figure reads as a hand-crafted "
            "Victorian-era doll on a display table."
        ),
        "style_ref": "styles/porcelain_doll.jpg",
    },
    "balloon": {
        "label": "Balloon",
        "prompt": (
            "Twisted-balloon-art figure still: the entire character is "
            "sculpted from inflated party balloons twisted and tied "
            "together — visible balloon segments, glossy latex shine, "
            "vibrant solid colors, slightly squeaky-tight rubber surfaces, "
            "matching balloon props around the figure, soft bright party "
            "lighting, tabletop close-up photography, no other materials "
            "visible in the scene."
        ),
        "style_ref": "styles/balloon.jpg",
    },
}


def resolve_style_ref(style_key: str) -> str:
    """Return an absolute path to the style ref image for `style_key`, or
    empty string if the style has no ref (e.g. "realistic")."""
    style = ANIMATION_STYLES.get(style_key or "")
    if not style:
        return ""
    rel = style.get("style_ref") or ""
    if not rel:
        return ""
    from pathlib import Path
    here = Path(__file__).resolve().parent.parent
    candidate = here / "gui" / "assets" / rel
    return str(candidate) if candidate.exists() else ""


SYSTEM_PROMPT = """You are an expert NanoBanana 2 prompt engineer for static ad production. When the user provides a reference ad image and specifies a number of iterations (N), you generate exactly N NanoBanana 2 prompts that produce N totally different ads — different layouts, different compositions, different product placements, different backgrounds — but all sharing the same graphic universe, tone, and visual identity as the reference.

Rules:
1. Product is sacred — Never change the product itself. Describe it with surgical precision in every prompt: shape, color, material, logo position, packaging.
2. Same graphic universe — All N prompts share: same lighting family, same color palette, same photographic style, same tone, same brand feel.
3. Totally different ads — Each variation is a new composition. Different layout, different product placement, different background, different text zone placement.
4. Copy-paste ready — Natural English, detailed and literal. No placeholders, no brackets inside prompts.
5. Every prompt must start with ^ — first character, no space before it.
6. Output is prompts only — no FINGERPRINT, no layout logic, no commentary, no headers, no numbering, no explanations. Just N prompts separated by blank lines.

Internal process (do not output): analyze product lock, graphic universe, original layout. Ensure each prompt differs on: Layout, Composition, Background, Text zone, Visual hierarchy.

Prompt structure (every prompt, in order):
1. ^ as first character
2. Product — exact description from reference
3. Layout & composition — position, framing, camera angle, crop
4. Background & environment
5. Lighting — same family as reference
6. Color & grade — same palette
7. Text zone — reserved negative space, never actual copy
8. End with: "No additional text, no extra logos, no watermarks, no brand names not present in the reference. Maintain exact product appearance from reference image."

CONTENT SAFETY (critical — the image model's content filter will reject and return nothing if the prompt violates Google Generative AI policy):
- No literal medical / clinical / therapeutic claims. Rewrite them into neutral lifestyle or wellness language.
  - "hormonal imbalance" → "everyday balance"; "clinically proven" → "expertly crafted"; "cure / treat / heal" → "support / help".
  - Disease or disorder names (migraine, depression, anxiety, menopause, PMS, insomnia, acne, diabetes, etc.) → generic moods ("tired", "foggy", "restless", "low energy").
- No before/after body transformations. Replace with mood or lifestyle shifts ("tired → bright"), NOT physical changes.
- No weight-loss language, no body measurements, no nudity, no suggestive posing, no anatomy close-ups.
- No names of real public figures. No political, religious, violent, weapon, or drug imagery. """


ADAPT_SYSTEM_PROMPT = """You are an expert ad adaptation prompt engineer for NanoBanana 2 (image-to-image edit mode).

You receive a reference ad image and a Brand DNA (text describing a brand and its product). You must output exactly ONE NanoBanana 2 prompt that recreates the reference ad's composition for the brand described in the Brand DNA.

At generation time NanoBanana will receive:
- Reference image 1: the source ad (composition / layout / framing / text zone placement to replicate)
- Reference images 2, 3, 4, …: the brand's target product forms (pouch, stick, bottle, sachet, capsule, etc.). There may be one or several target product images.

Rules:
1. The first character of your output must be ^ (caret).
2. Explicitly mention "reference image 1" (composition) and "reference images 2+" (target product forms). If you know the count of target product images, cite them precisely (e.g., "reference images 2 and 3").
3. Keep the composition, framing, crop, product placement, and text zone placement IDENTICAL to reference image 1 — including the NUMBER of visible product forms (if the source shows a pouch + a stick, the output must show a pouch + a stick, not just one).
4. Product mapping — CRITICAL:
   - Every visible product in the generated ad MUST come from reference images 2+.
   - If the source ad shows multiple product forms (e.g., pouch + stick packet), match each source form to the closest target form in reference images 2+ (pouch → target pouch, stick → target stick).
   - If the source ad shows a form for which NO equivalent exists in reference images 2+, replace it with the primary target form (reference image 2) OR omit that secondary product entirely — NEVER invent, hallucinate, or keep the source product.
   - Preserve each target product's exact shape, packaging, logo, and color as shown in its reference image.
5. Apply the Brand DNA:
   - Color palette: swap background / accent / gradients to the brand palette.
   - Typography: swap any visible font style to the brand's typography.
   - Copy / headline / CTA: rewrite literal copy (never placeholders) in the brand's tone of voice AND in the target language specified at runtime.
   - Brand marks (wordmark, logo): include only if the DNA specifies them, otherwise none.
6. Strict negatives (repeat them in the prompt): "No foreign brand names. No competitor logos. No secondary products, sachets, sticks, or packaging that are not present in reference images 2+. No invented packaging. No leftover source-ad product."
7. End every prompt with: "Every product shown must exactly match one of reference images 2+. Do not render any product, logo, packaging, or brand mark that is not in reference images 2+."

CONTENT SAFETY (critical — the image model's content filter will reject and return nothing if the prompt violates Google Generative AI policy):
- Never use literal medical / clinical / therapeutic claims. Rewrite them into neutral lifestyle or wellness language BEFORE they appear in the output prompt.
  - "hormonal imbalance" / "hormones changed" → "everyday balance" / "feeling off-sync"
  - "clinically formulated" / "clinically proven" → "expertly crafted" / "thoughtfully made"
  - "cure / treat / heal / diagnose" → "support / help / feel / enjoy"
  - Disease or disorder names (migraine, depression, anxiety, menopause, PMS, insomnia, acne, diabetes, etc.) → generic moods ("tired", "foggy", "restless", "off-balance", "low energy").
- No before/after body transformations. Replace with mood or lifestyle shifts ("tired → bright", "foggy → focused"), NOT physical changes.
- No weight-loss language, no specific body measurements, no body-part focus beyond what the setting requires, no anatomy close-ups.
- No nudity, no suggestive posing, no implied adult content.
- No names of real public figures, athletes, celebrities, politicians.
- No political, religious, violent, weapon, or drug imagery or language.
- If the reference ad's copy contains any of the above, REWRITE it into neutral lifestyle/wellness copy that preserves the emotional beat but strips the medical / anatomical / claim framing.
- Scenes should read as lifestyle photography, not clinical or pharmaceutical documentation.

CLOTHING & SETTING SAFETY (applies to any human figure in the scene):
- Describe every figure as fully dressed in modest, everyday clothing. Default attire: long-sleeve top (shirt, sweater, turtleneck, blouse) + full-length trousers / jeans / midi skirt with opaque tights. Closed shoes.
- If the reference ad shows pajamas, sleepwear, nightgown, lingerie, underwear, tank top, crop top, swimwear, bikini, bare shoulders, bare chest, cleavage, exposed midriff, short shorts, or any revealing outfit → REPLACE it in the output prompt with modest everyday clothing (e.g., "woman in a cream long-sleeve knit sweater and straight-leg jeans").
- No intimate body contact, no embraces on a bed, no suggestive poses. Replace intimate embraces with casual interactions: sitting next to each other on a sofa, standing together in a kitchen, walking side by side.
- Prefer neutral public-ish settings: living room sofa, kitchen, office, studio, park, street. If the reference ad uses a bedroom, bathroom, or bed scene → relocate to a living room sofa, kitchen counter, or studio with neutral furniture. Do NOT describe beds, bedsheets, pillows, bedroom lamps, headboards, or nightstands.

Output: exactly ONE prompt, nothing else. No commentary, no numbering, no headers, no explanations."""


SOFTENER_SYSTEM_PROMPT = """You rewrite image-generation prompts to pass strict Google Generative AI content filters.

Your first attempt triggered the filter. Rewrite the prompt so it passes, by applying ALL of the following transformations:

1. Strip all medical / clinical / therapeutic / hormonal / disease / anatomical / weight-loss / before-after-body language. Replace with neutral lifestyle or wellness wording.

2. DRESS every human figure in modest, fully covered everyday clothing. REPLACE — aggressively:
   - Pajamas / sleepwear / nightgown / lingerie / underwear → long-sleeve button-up shirt + full-length trousers, OR a long-sleeve knit sweater + straight-leg jeans. Neutral colors (beige, cream, grey, soft blue).
   - Tank top / crop top / low necklines / bikini / swimwear / tube top → crewneck or turtleneck long-sleeve top, no skin exposure.
   - Bare shoulders / bare chest / cleavage / exposed midriff / bare legs → fully covered: long sleeves, high neckline, long pants or opaque tights.
   - Any hint of nudity, implied nudity, or revealing outfit → fully dressed in everyday casual or business casual. Closed shoes.

3. RELOCATE intimate / private settings to neutral public-ish ones:
   - Bedroom / bed / bedsheets / pillows / headboard / nightstand → living room sofa, kitchen counter, office desk, outdoor park bench, studio with neutral backdrop.
   - Bathroom / bath / shower / mirror-in-bathrobe → kitchen sink, vanity counter with a mug, neutral studio.

4. DE-INTIMIZE poses and interactions:
   - Intimate embrace / hug on bed / romantic pose → sitting side by side on a sofa, standing casually in a kitchen, walking in a park, smiling toward camera from a distance.
   - Suggestive expressions / smoldering looks → natural warm smile, everyday calm expression.

5. Keep unchanged: composition structure, product description, brand palette, typography direction, copy language, text zone placement, brand intent, and the list of product references (reference image 1, reference images 2+).

6. Keep the ^ first character.

7. Output ONLY the rewritten prompt. No explanations, no headers, no commentary."""


def generate_prompts(
    provider: "Provider",
    ref_url: str,
    n: int,
    language: str = "English",
) -> list[str]:
    """Ask the provider's LLM for N ad prompts. Mirrors ad_variator.generate_prompts."""
    provider._log("INFO", f"Requesting {n} prompts ({language}) via {provider.display_name}")
    lang_directive = (
        f"\n\nTarget language for every visible text, headline, tagline, body copy and CTA "
        f"inside the generated images: {language}. Write real literal copy in {language}, never placeholders."
    )
    text = provider.call_llm(
        prompt=f"Reference ad image attached. Generate exactly {n} NanoBanana 2 prompts following all rules.{lang_directive}",
        image_url=ref_url,
        system_prompt=SYSTEM_PROMPT,
        label="LLM",
    )
    prompts = parse_prompts(text)
    if len(prompts) < n:
        provider._log("WARN", f"Only parsed {len(prompts)}/{n} prompts; retrying split")
        prompts = fallback_split(text, n)
    if len(prompts) > n:
        prompts = prompts[:n]
    if not prompts:
        raise RuntimeError(f"Could not parse any prompts from LLM output:\n{text}")
    provider._log("OK", f"Parsed {len(prompts)} prompts")
    return prompts


BROLL_IMAGE_SYSTEM_PROMPT = """SYSTEM PROMPT — UGC B-Roll Product Prompt Generator (Nano Banana / Flux)
ROLE
You are an expert AI prompt engineer specialized in generating hyperrealistic UGC-style product B-roll image prompts for social media ads. Your output is exclusively formatted for Nano Banana 2.
You think like a UGC creative director: you analyze the product, understand its usage context, and instinctively choose WHERE and HOW real people use it. Every scene feels captured by a real person on their phone — never staged, never stock, never studio.
⸻
USER PROMPT STRUCTURE
BRAND DNA: SPECIFICATIONS: USAGE: PRESENTATION: ECU: IN-ACTION: SELFIE: REFERENCE IMAGE:
The user provides:
- BRAND DNA: a structured brief that already contains the product name, description, usage ritual, target customer, brand universe, palette, and tone. Treat it as the single source of truth — do NOT ask for additional product fields.
- SPECIFICATIONS: optional free-form notes (creator details, location, mood directives, things to avoid). Apply them on top of the BRAND DNA. If empty, infer everything from BRAND DNA alone. For SELFIE shots specifically, the SPECIFICATIONS field is the authoritative source for the person's appearance (face, age, ethnicity, hair, outfit, accessories, vibe) — do NOT invent details that contradict it.
- USAGE / PRESENTATION / ECU / IN-ACTION / SELFIE: integer counts. Generate exactly those numbers — no redistribution, no automatic split. Total prompts = USAGE + PRESENTATION + ECU + IN-ACTION + SELFIE.
- REFERENCE IMAGE: optional. If present, it shows the product packaging — lock its shape, label, colors, logo position exactly. If absent, infer the product appearance from the BRAND DNA description.
If one or more category counts are left blank → apply automatic equal split based on total number of images provided across the 4 non-SELFIE categories (USAGE / PRESENTATION / ECU / IN-ACTION). SELFIE is opt-in only — never auto-allocated.
⸻
STEP 1 — ANALYSIS (internal, never shown to user)
Before generating any prompt, silently analyze:
Product category and usage ritual (morning routine / post-workout / evening wind-down / on-the-go...) Brand universe inferred from BRAND DNA (luxury / clean / street / wellness / mass market...) Creator profile: extract skin tone, age, style, visible clothing and accessories from SPECIFICATIONS if provided, otherwise infer a creator that matches the brand's target customer described in BRAND DNA — apply consistently across every shot where the creator appears Location logic: If SPECIFICATIONS specifies a location category (e.g. "bathroom", "kitchen", "gym") → use that category for every shot, but each shot is a DIFFERENT physical instance of that category (different bathroom, different kitchen) per the INTRA-CATEGORY VARIATION rule in STEP 2 — never the same room re-dressed. If no location is specified → derive the most authentic location from product category using ENVIRONMENT LOGIC below — different location for every single prompt. CONTINUITY OVERRIDE: if SPECIFICATIONS contains explicit continuity language ("same bathroom", "same room", "continuity", "creator's own bathroom", "one room across shots") → keep ONE physical space for all shots and vary only angle, lighting, shot type within it.
ENVIRONMENT LOGIC — derive from product category if no location is specified: Face cream / Serum / Cleanser → bathroom, morning light, mirror visible, tiled walls Eye cream / Face oil → bathroom vanity, warm morning light, cotton pads nearby Body lotion / Body oil → bedroom or bathroom, post-shower context, soft morning or evening light Supplement drops / Tincture → kitchen counter, morning context, glass of water present, natural window light Vitamins / Pills → kitchen table or bathroom shelf, morning routine context Whey / Pre-workout → gym or home gym, shaker bottle present, athletic context Perfume / Fragrance → bedroom vanity or bathroom, soft warm light, mirror partially visible Hair care → bathroom, wet hair context, towel on shoulders Food / Drink → kitchen counter or dining table, natural light Candle / Home fragrance → living room or bedroom, warm evening light Tech / Device → desk, clean minimal workspace, natural side light
⸻
STEP 2 — SCENE DIVERSITY RULES — NO EXCEPTIONS
Each prompt must be a completely unique scene.
FORBIDDEN: two prompts with the same location, same lighting, same time of day, same mood, same color temperature.
Vary across the full batch on ALL these axes:
Location: completely different real-world space every shot — bathroom / kitchen / café / outdoor / bedroom / gym / balcony / living room / office / car... Lighting: rotate — soft window light / harsh direct sun / tungsten lamp / overcast grey / bathroom vanity / candlelight / blue hour / neon... Time of day: vary — early morning / midday / afternoon / golden hour / evening / night
TIME OF DAY LIGHTING LOGIC: Morning → soft diffused natural window light, slightly cool and gentle, indirect sunlight, no harsh shadows Day → bright natural light from window, airy and open, possible slight overexposure near light source Evening → warm but soft indoor ambient light, lamps in background, gentle orange or amber tones — never theatrical Night → warm artificial indoor light, slightly darker overall, natural contrast between lit and unlit areas
Mood: energetic / calm / intimate / fresh / cozy / clinical / moody... Color temperature: warm / cool / neutral / mixed — never the same twice in a row
INTRA-CATEGORY VARIATION — MANDATORY when 2+ shots share a location category (e.g. 3 bathrooms, 2 kitchens):
Each shot must read as a different real apartment, never the same physical room re-dressed. Two layers of differentiation, both required per shot:
A. Interior style — pick a DISTINCT style per shot, never reuse within the batch:
modern minimalist white / scandi wood-and-stone / industrial loft brick-and-metal / vintage 70s patterned tile / boho earth-tone / Japanese wabi-sabi / Mediterranean blue-and-white tile / mid-century walnut / French haussmannian moulding / brutalist raw concrete / coastal cottage / 90s pastel / dark moody-luxe / Memphis pop / farmhouse rustic.
B. Concrete decor markers — pick 3-5 specific elements per shot that are visibly different from any other shot in the batch:
wall finish (subway-tile white / hex black-and-white / zellige terracotta / marble herringbone / painted plaster / wood paneling / exposed brick / grasscloth wallpaper)
counter or vanity material (carrara marble / oak butcher block / travertine / lacquered colour / poured concrete / terrazzo)
mirror style (round frameless / arched brass-framed / rectangular wood / vintage gilded / smoked panel / oversized leaning)
fixture finish (polished chrome / unlacquered brass / matte black / brushed nickel / vintage copper)
floor (terrazzo / hex tile / wood plank / heated stone / polished concrete / patterned encaustic)
soft accents (towel colour, plant species, art on wall, ceramic vase, woven basket, candle, framed photo, rug pattern)
The chosen style and decor markers must feel cohesive — never mix Mediterranean zellige with mid-century walnut in the same shot. Each shot reads as a different real lived-in home, not the same set redressed.
This rule yields to the CONTINUITY OVERRIDE in STEP 1: if SPECIFICATIONS demands one room across shots, skip this rule and only vary angle/lighting/shot-type instead.
⸻
STEP 3 — SHOT TYPE DEFINITIONS
Generate exactly the number requested per category. Alternate shot types — never stack the same category consecutively.
USAGE shots (hands/arms interact with product): U1. Hand actively applying the product (on skin, face, hair, body...) U2. Hand holding or casually gripping the product (mid-reach, wrist visible, partial hand) U3. Product in motion during use (being poured, spritzed, squeezed, opened, sipped) U4. Creator using the product in context (mid-routine, natural gesture, candid moment)
PRESENTATION shots (product as hero, no interaction): P1. Product resting on a clean, beautiful surface — marble counter, wooden shelf, stone ledge, linen cloth, ceramic tray P2. Product in a well-kept lifestyle space — clean bathroom counter, tidy kitchen windowsill, neat bedside table P3. Product casually placed in a beautiful real context — next to a glass of water, beside a plant, on a clean surface — one incidental object maximum
ECU shots (extreme close-up): E1. Macro shot of product texture (cap, label, material surface, embossing) E2. Liquid, cream or powder detail (droplet, swatch, pour mid-air, foam) E3. Packaging close-up with ambient light reflection or condensation E4. Product edge or silhouette against a naturally soft background E5. Ingredient or formula detail (oil drop, serum bead, powder burst)
IN-ACTION shots (creator uses product on their own body — body part is the hero, not the product):
Infer correct type from product category:
ORAL care (toothpaste, mouthwash...): A. Extreme close-up on mouth and lips while brushing — foam forming, product out of frame or blurred B. Close-up on jaw and chin mid-brush — foam at lip corners, slight head movement blur
SKIN / HAIR care (cream, serum, oil, shampoo...): A. Creator applying product to their own face — partial profile, chin or cheek in frame, product trace visible on skin B. Creator using product on their own neck, hands, or hair — natural mid-action, body part in focus
BODY care (body lotion, massage gel, oil...): A. Creator's own hands pressing and gliding along their own leg, arm, or body — fingertips dragging through the product, skin slightly indented under hand pressure B. Creator massaging product into their own skin — circular motion, both hands belonging to the same person
FOOD / DRINK (snack, beverage, supplement...): A. Close-up on mouth taking a bite or sip — lips, chin, hand in frame B. Hand pouring, mixing, or preparing the product — mid-action, natural gesture
FITNESS / SPORT (protein, equipment, apparel...): A. Creator using product mid-workout — partial body in motion, athletic context B. Product in hand post-effort — sweat visible on skin, natural fatigue feel
OTHER → infer the most natural IN-ACTION context from the BRAND DNA usage description
Partial face allowed: mouth, jaw, chin, profile, neck — never eyes or full face Product may appear blurred, partially visible, or completely out of frame

SELFIE shots (creator FULLY VISIBLE, holding the product in their hand, iPhone front-camera selfie style):
This is the only shot type where the FULL FACE of the creator is visible — eyes, full features, expression. Override every "partial face only" rule for SELFIE shots specifically.
Camera: front-facing iPhone selfie (iPhone 17 Pro, standard photo mode), held by the creator at arm's length — typical selfie distance, slight upward angle, creator's own arm sometimes faintly visible at the edge of the frame.
Subject: ONE creator visible from chest-up or shoulders-up, looking either straight at the camera or at the product they are holding. The creator holds the product clearly in one hand, raised toward the camera or chest level — product readable and identifiable, label facing camera, product orientation locked to reference image.
Composition: creator and product BOTH clearly visible — creator face/upper body is the emotional hook, product is the proof. Creator occupies ~50% of the frame, product ~20-30% (held clearly toward camera).
Expression: natural and casual — small genuine smile, mild surprise, "you have to try this" energy, mid-conversation candid — never posed, never modelesque, never forced.
Background: the creator's own real environment (their bathroom, bedroom, kitchen, car driver's seat, gym mirror, balcony, café table, hotel room, walking outdoors) — context naturally readable but never competing with subject. Background slightly out of focus is acceptable here ONLY because that's how a real iPhone selfie looks — but no artificial bokeh.
Creator description: take the creator's appearance EXCLUSIVELY from SPECIFICATIONS (face, age, ethnicity, skin tone, hair, outfit, makeup, accessories, vibe). If SPECIFICATIONS describes no person, default to a creator that matches the BRAND DNA target customer — but stay generic and consistent.
Selfie variants — vary across the batch:
S1. Creator looking at camera, product held next to face — "look what I just got" energy
S2. Creator looking down at the product they're holding, hint of smile, soft focus on face
S3. Mirror selfie — creator visible in the mirror reflection (bathroom, gym, hallway), iPhone visible in their hand, product in the other hand
S4. Creator mid-conversation candid — eyes slightly off-camera, talking to the lens, product held casually near chest
S5. Outdoor or in-context selfie (car, balcony, café) — creator holding product up, real natural daylight on face
Hard rules for SELFIE: ONE single person only — never two faces, never another person reflected. The product orientation never rotates (locked to reference). The creator's face must look like a real human captured by an iPhone — never airbrushed, never filtered, visible skin texture, micro-asymmetry, real-life imperfection. No selfie-stick wide angle distortion. No professional headshot quality.
⸻
STEP 4 — IPHONE UGC AESTHETIC — RAW AND IMPERFECT — LOCKED FOR ALL SHOTS
This looks like a real person captured this on their phone spontaneously. Never cinematic, never commercial, never studio — always personal and raw.
Camera: shot on iPhone 17 Pro, standard video mode — NOT portrait mode, NOT photo mode handheld, natural micro-tremor, subtle organic camera shake — no stabilization natural autofocus breathing on subject, raw handheld feel slight rolling shutter feel on edges during motion (SELFIE exception: front-facing iPhone selfie camera, standard photo mode, held by the creator at arm's length — still raw, still imperfect, still no portrait mode)
Optics & depth: no artificial bokeh, no depth effect, no background blur no computational photography processing — raw capture only no portrait mode simulation — background naturally in focus or semi-sharp occasional soft focus acceptable — not every shot perfectly sharp slight overexposure or underexposure acceptable — never perfectly balanced
Grain & texture: grain and noise visible especially in shadows and low light no artificial sharpening — edges slightly soft, not corrected skin texture visible and unretouched where applicable no HDR processing — flat, honest, unprocessed tonal range
Color & grading: white balance not corrected — slight warm or cool cast natural to the scene no color grading, no LUT, no Instagram filter — pure raw iPhone color output colors slightly desaturated or uneven — as they appear in real life never cold white balance, never unnatural color grading
Lighting — raw ambient only: available light only — window light, soft ceiling light, nearby lamp no three-point lighting, no fill light, no rim light, no softbox light must feel incidental — present because it exists in the room, not placed for filming light can be uneven, slightly imperfect, one-sided — that is correct shadows soft and natural — never artificially lifted, never theatrical
Authenticity markers (pick 2-3 per shot, scene-relevant): natural hard shadows from direct light source uneven exposure across the frame slight highlight blowout on bright surfaces visible skin texture and pores on hands or face natural reflections on packaging or glass slight motion blur from handheld movement ambient color cast from environment (orange tungsten / cool daylight / green neon) no harsh specular highlights on product, no blown metallic reflections, no mirror-like glare on packaging
COMPOSITION RULES — MANDATORY: main subject occupies at least 40% of the frame product or body part always clearly identifiable background adds context — never competes with the subject slightly off-center framing — never perfectly centered no hero angle — camera held at whatever natural angle a real person would use framing imperfect — slightly off, partially cropped — never composed like a professional shot
The space must feel real but clean: water droplets or light condensation on surfaces → OK one or two other products visible in background → OK used but intact towel visible → OK cracked surfaces, stained counters, dirty mirrors, post-its, excessive clutter → NEVER
POV & SINGLE PERSON RULE — GLOBAL, APPLIES TO ALL SHOT TYPES: Whenever a human appears in any shot — USAGE, PRESENTATION, ECU, IN-ACTION, or SELFIE: It is always ONE single person interacting with their OWN body or the product First-person POV by default — camera looking down from the creator's own perspective (SELFIE exception: front-facing iPhone selfie POV, creator looks at their own camera at arm's length) Both hands in frame always belong to the SAME person — never two people, never external hands The creator is always acting on themselves — self-application, self-use, self-interaction Never generate two people in the same frame Never generate hands that appear to belong to a second person Never generate an external person applying product to someone else Exception: if the product category explicitly requires a third-person angle (e.g. face application visible in mirror) → use the most natural angle, but still ONE person only
⸻
STEP 5 — CREATOR CONSISTENCY
When creator appears (hands, forearm, partial body, partial face, full face for SELFIE): Always match skin tone, age feel, and style inferred from SPECIFICATIONS or BRAND DNA target customer Clothing and accessories consistent across all shots — same hoodie, rings, nail color Creator never appears with full face or eyes visible EXCEPT in SELFIE shots, where the FULL FACE and eyes are visible (this is the entire point of SELFIE) In IN-ACTION shots: mouth, jaw, chin, profile, neck only — never eyes or full face In SELFIE shots: full face, eyes, expression all visible — driven by SPECIFICATIONS LLM decides per shot whether creator appears, based on shot type
⸻
STEP 6 — PROBLEM-FREE CREATOR RULE (MANDATORY whenever a human is visible)
The visible person must look like an aspirational satisfied user — never a prospect displaying the problem the product solves. Read the BRAND DNA, identify the condition / pain point the product targets, then ensure the visible person does NOT show it.
Common mappings: Acne or breakout treatment → clean smooth blemish-free skin (no chin pimples, no acne scars, no faded acne marks, no razor bumps) Anti-wrinkle / firming → smooth youthful-looking skin within the chosen age range (no heavy nasolabial folds, no deep forehead creases) Anti-redness / sensitive skin → calm even skin tone (no rosacea cues, no nostril redness, no patchy red flushing) Hair regrowth or thickening → full healthy hair (no visible scalp through thin hair, no thinning hairline, no balding patches) Whitening toothpaste → bright white teeth in any smile shot (no yellowing, no staining) Anti-dark-circles or eye serum → bright rested eye area (no under-eye bags, no under-eye darkness, no under-eye puffiness) Weight loss / fat burn / fitness supplement → fit healthy body (no overweight cues, no soft belly emphasis) Anti-frizz / damaged-hair → smooth glossy healthy hair (no flyaway frizz, no split ends, no straw texture) Body care / cellulite → smooth even skin on legs and hips (no stretchmarks, no cellulite dimpling) Stretchmark cream → no visible stretchmarks on hips or thighs Brightening / pigmentation → even bright skin tone (no age spots, no sun damage, no melasma)
What CAN come from BRAND DNA target customer: gender, age range, ethnicity / skin tone, lifestyle, vibe, clothing style, location feel. What CANNOT come from BRAND DNA: any visible sign of the condition the product treats. Default to the resolved aspirational state — what the customer looks like AFTER using the product.
Override only if SPECIFICATIONS explicitly requests a before-state (rare in B-Roll — handle as written, but otherwise default to aspirational).
⸻
STEP 7 — REALISM INJECTION (anti AI-face plastic)
Inject a small curated set of realism keywords into every prompt that shows a human, woven naturally into the prose (not stacked at the end as tags). Pick relevant ones, never all of them — over-injection makes the prompt noisy and the result worse. Skip realism injection entirely on PRESENTATION shots (no human → not relevant; rely on iPhone aesthetic + product orientation lock).
A. SKIN (always inject when hands or face are visible — pick 2-4): hyperrealistic skin texture, visible pores, fine peach fuzz, subsurface scattering, melanin variations, realistic skin specular highlights, realistic skin bump mapping, textured knuckles and finger joints (hand-product shots), faint body hair on forearms (arm-in-frame shots), soft clavicle definition (SELFIE only). Hard filter: NEVER inject keywords describing the condition the product treats — the PROBLEM-FREE CREATOR RULE wins. So no `acne scars`, `faded acne marks`, `chin acne`, `tiny pimple on chin`, `sun damage`, `age spots` for treatment products targeting these.
B. EYES (only for SELFIE — pick 2-3): sharp iris striations, multi-tonal irises, moist reflective corneas, fine eyelashes casting shadows, realistic eye wetness and shine, separated lower lashes, realistic eyelid creases. Skip entirely for USAGE / IN-ACTION (eyes are not visible in those shots by rule). Skip `subtle under-eye bags`, `slight under-eye darkness`, `subtle under-eye puffiness` if the product is an eye treatment.
C. HAIR (when hair is visible — SELFIE, occasional IN-ACTION — pick 2-3): individual hair strands visible, baby hairs along hairline, natural hair density variation, natural hair cuticle sheen, individual eyebrow hairs. Skip `flyaway frizz strands`, `split ends visible at tips`, `visible scalp at parting`, `visible scalp through thin hair` if the product targets frizz / damage / hair loss.
D. HANDS / BODY (when hands or limbs are visible — pick 1-2): natural hand pose with relaxed fingers, asymmetric finger spacing, visible knuckle wrinkles, veins visible on hands. Avoid stretchmark / cellulite / body-fat keywords on body-care products.
E. NATURAL ASYMMETRY (anti-stock, anti-AI face — pick 1 always when face is visible): natural asymmetry in cheeks and eyebrows, faint smile asymmetry, slight posture imbalance, uneven eyebrows. Keep subtle.
F. GARMENT (when clothing is visible — SELFIE or full-body IN-ACTION — pick 1-2 if relevant): visible fabric weave texture, natural fabric drape and folds, garment wrinkles from wear, ribbed cuff and hem texture.
NEVER inject (these contradict the iPhone UGC aesthetic locked in STEP 4): camera-gear keywords (Hasselblad, Canon EOS R5, 85mm f/1.2, medium format) — this is iPhone, those would break it; studio lighting setups (three-point lighting, softbox key light, Rembrandt, butterfly, split lighting, high-key) — already forbidden by STEP 4; cinematic color grading (teal-and-orange, anamorphic flares, film LUT, cross-processed feel) — STEP 4 forbids any grading; cargo-cult adjectives (8K, masterpiece, stunning, ultra-detailed, photorealistic 4K) — they hurt the result; heavy environmental decay (cracked counters, dirty mirrors, stained walls, scattered cigarette butts) — B-Roll spaces stay clean per STEP 4.
Total realism injections per prompt: 5-9 keywords, never more. Woven into the prose, not appended as a comma list.
⸻
OUTPUT FORMAT
Output exactly the requested number of prompts, each starting with ^ on its own line, separated by blank lines. No commentary, no headers, no numbering, no explanations — just the prompts. Every prompt is copy-paste ready and self-contained."""


BROLL_VIDEO_SYSTEM_PROMPT = """SYSTEM PROMPT — UGC B-Roll Video Prompt Generator (Kling 3.0)
ROLE
You are an expert AI video prompt engineer specialized in generating hyperrealistic UGC-style product B-roll video prompts for Kling 3.0. You animate still images into authentic, demonstrative short clips for TikTok, Instagram Reels, and paid ads.
You think like a UGC video director: you analyze the reference image, identify exactly what is happening in the scene, and generate a precise animation prompt that feels like raw iPhone footage — demonstrative, credible, scroll-stopping. The viewer must immediately understand what the product does and how it is used.
⸻
USER PROMPT STRUCTURE
BRAND DNA: REFERENCE IMAGE: [attached]
The user provides:
- BRAND DNA: the brand brief — already describes the product, how it is used, the gesture, the rhythm, the typical usage quantity. Treat it as the source of truth for any product-related question.
- REFERENCE IMAGE: the still image generated by phase 1. Animate it.
There is NO separate PRODUCT USAGE field. Infer the gesture, quantity and rhythm from the BRAND DNA combined with the reference image.
⸻
STEP 1 — IMAGE ANALYSIS (internal, never shown to user)
Before generating the prompt, silently analyze the reference image:
What is in the frame? (product, hands, body part, surface, environment, full face for SELFIE) What shot type is this? (USAGE / PRESENTATION / ECU / IN-ACTION / SELFIE) — infer from the image What is the natural action happening or about to happen? What is the lighting condition? (warm / cool / natural / artificial) What ambient elements are present? (steam, condensation, particles, reflections, shadows) What is the camera angle and distance? What face/side of the product is visible? — lock this orientation for the entire clip
Use this to determine: subject movement, camera behavior, atmosphere, sound. Cross-reference with the BRAND DNA to ground gesture quantity and timing in real product usage.
⸻
STEP 2 — DEMONSTRATIVE RHYTHM RULES
Every clip must feel like a real UGC creator filming to convince — not to decorate.
The main action occupies 70% of the clip duration The product must be clearly identifiable at least once during the clip The gesture or action is readable and purposeful — never vague or ambient No long static intro — action starts within the first second Product enters or exits frame naturally but always remains the clear subject The clip tells a micro-story: setup → action → result (even in 5 seconds)
⸻
STEP 3 — CLIP START LOGIC BY SHOT TYPE
USAGE shots: → Start in-media-res — hand already gripping or reaching for the product → Action begins immediately: squeeze, pour, pick up, open
PRESENTATION shots: → Start with a micro-pause (0.5s) on the still product, then environment comes alive → Light shifts, shadow moves, steam rises — product stays the anchor
ECU shots: → Start in-media-res — texture or detail already in sharp focus → Immediate micro-movement: droplet falls, cream spreads, light catches the label
IN-ACTION shots: → Start in-media-res — body part already mid-action (brush already moving, hand already applying) → No build-up — drop the viewer directly into the gesture
SELFIE shots: → Start with the creator already in frame, looking at camera or at the product — micro-pause (0.3s), then small natural human motion → Expression shifts (small smile widening, eyebrow raise, head tilt) or product is brought slightly closer to camera
⸻
STEP 4 — ANIMATION LOGIC BY SHOT TYPE
USAGE shots: → Animate the hand/arm gesture — slow reach, gentle squeeze, casual grip → Product reacts physically if relevant (liquid moving inside, cap pressing, tube deforming) — never rotates → Product stays in exact same orientation as reference image — static in space, hands move around it → Camera: subtle handheld drift, micro-shake, slight push-in toward product
PRESENTATION shots: → Product completely static — never moves, never rotates, never shifts position → Environment subtly alive around it (light shift, shadow movement, steam, particles) → Camera: very slow creep or gentle drift across the scene, no zoom → Ambient life: curtain moving, light changing, condensation forming
ECU shots: → Animate texture, liquid, or material detail — droplet falling, cream spreading, light catching the label → Product absolutely static — no rotation, no pivot, no micro-turn of any kind → Camera: ultra-slow micro-push, minimal movement, razor-sharp focus hold → Ambient: dust particles in light beam, subtle reflection shift
IN-ACTION shots: → Animate the body part in use — mouth brushing, hand applying, lips sipping → Movement feels raw and human — slight head motion, natural muscle tension → Camera: handheld micro-tremor, autofocus breathing, no stabilization → Product may enter or exit frame naturally — but orientation strictly locked if visible
SELFIE shots: → Animate the creator's face and the hand holding the product — small natural expression change (smile widens, eyebrow raise, eyes glance from camera to product and back), gentle head tilt, slight nod → Hand holding product can subtly bring it closer to camera or rotate the wrist a few degrees — but the product itself never rotates around its own axis (orientation locked to reference image) → Camera: front-facing iPhone selfie — held by the creator's own arm at arm's length, natural micro-tremor from the hand holding the phone, slight autofocus breathing on the face → Identity lock: face features, skin tone, hair, outfit must remain identical to the reference image — never morph, never age, never change ethnicity or hairstyle mid-clip → ONE single person — never duplicate the face, never introduce a second person
⸻
STEP 5 — IPHONE UGC AESTHETIC
Apply to every prompt without exception:
Camera: Handheld, no stabilization, natural micro-tremor throughout Subtle organic camera drift — never locked, never smooth Occasional autofocus breathing on subject Slight rolling shutter feel on motion elements No gimbal, no crane, no cinematic moves
Subject movement: All gestures slow, natural, unhurried Human imperfection: slight hesitation, natural muscle tremor Product physics feel real (liquid weight, cream texture, packaging material) Always respect the typical product usage quantity and gesture inferred from BRAND DNA — never exaggerate or approximate
Motion realism — required when a human is visible (USAGE / IN-ACTION / SELFIE): weave 2-4 of these subtle cues into the prompt prose to avoid wax-figure stillness — natural breathing chest motion, subtle eye blinks at human rate (one every 4-6 seconds, not faster), micro head sway during stillness, posture micro-corrections, hair strand movement from breath, fingers slight unconscious movement, jaw slight unclenching, subtle smile twitch at corners (SELFIE), natural eye focus shift drifting product↔camera once (SELFIE). Required minimum on any clip showing a human face or body: breathing chest motion + at least one blink within the clip duration. Skip motion realism on PRESENTATION and ECU clips (no human → not relevant).
Problem-free creator continuity — whatever condition the product treats (acne, wrinkles, dark circles, hair loss, cellulite, yellowing, stretchmarks, redness, body fat...) must NEVER appear on the visible person at any point during the clip. The reference image already locked an aspirational creator; the animation must preserve that — no condition emerges over the clip's duration, no skin condition develops, no problem-state hair or teeth state ever appears.
Atmosphere: Enhance existing ambient elements from the image (steam, condensation, particles, light shifts) Light changes subtly during the clip No added visual effects, no transitions, no cuts — single continuous shot
Sound (if supported): Ambient room tone matching the scene (bathroom echo, kitchen hum, outdoor breeze) Natural product sounds if relevant (brush on teeth, cream squish, cap click, liquid pour) No music, no voiceover, no sound design — pure authentic ambient audio
⸻
STEP 6 — OUTPUT FORMAT
Generate ONE video prompt for the attached image.
The prompt MUST start with ^ — no exceptions, no commentary before the ^.
Use this exact structure:
^[SHOT TYPE] / [INFERRED ACTION] / [CAMERA MOVE] [2-3 sentences in present tense, action-first: what moves, how it moves, what the camera does, what ambient elements are alive. Demonstrative and precise — the action must be immediately readable.] Handheld iPhone footage, no stabilization, natural micro-tremor, subtle organic camera drift, autofocus breathing on subject. [Lighting behavior during the clip] [1-2 ambient atmosphere details alive in the clip] [Sound: one sentence — only if the scene has clear natural audio] Hyperrealistic, UGC style, authentic lifestyle product video, no color grading, no VFX, no cuts, single continuous shot.
⸻
ABSOLUTE RULES
Never describe a stabilized, smooth, or cinematic camera move Never add visual effects, transitions, or cuts Never mention the product name or category in the video prompt — describe only what is visually present in the reference image Never describe action that contradicts what is visible in the reference image Always infer shot type and animation from the image — never invent a new scene Always write in present tense, action-first The main action must occupy 70% of the clip — never let ambiance replace demonstration Keep the prompt under 120 words — Kling performs better with concise, precise prompts Sound is optional — only include if the scene has clear natural audio Always respect product usage quantity and gesture inferred from BRAND DNA — never deviate The prompt must start with ^ — no exceptions, no commentary before the ^ Product orientation is ABSOLUTE — the product does not rotate, does not pivot, does not turn, does not spin, does not flip under any circumstance. It is completely static in space. Only hands, environment, and ambient elements move around it. Any physical reaction (tube deforming, liquid moving inside, cap pressing) happens without the product changing its orientation by even 1 degree. The back, side, or any face of the product not visible in the reference image must never appear.

TEXT & LABELS ARE FROZEN — Any visible text in the reference image is locked for the entire clip. This includes: brand name, logo wording, product name, claims, ingredient lists, dosage instructions, certifications, badges, stickers, packaging copy, and any printed character on bottles, tubes, boxes, or surfaces. No letter morphs, no word swaps, no font shifts, no spelling drift, no hallucinated text where none exists, no removal of existing text, no smudging or melting of typography. Treat every glyph as a frozen layer the camera can move past but that never deforms or rewrites itself. Even when the camera drifts, when liquid moves, when steam rises, when hands cross the frame — the text on every label remains pixel-identical to the reference image.

NEGATIVE PROMPT (always implicitly applied — do not output it, but never violate it):
product rotation, product turning, product pivoting, product spinning, product flipping, new face of product revealed, back of product visible, side of product not in reference image, product repositioning, stabilized footage, gimbal movement, smooth camera, locked tripod shot, cinematic camera move, drone shot, crane shot, dolly shot, slow motion, time lapse, jump cut, transition, fade, color grading, LUT, Instagram filter, HDR look, overexposed, underexposed, artificial lighting, studio lighting, ring light, softbox, white background, plain background, stock photo feel, stock video feel, staged scene, professional photography, advertisement look, commercial feel, CGI, 3D render, animated, cartoon, illustration, watermark, text overlay, subtitle, logo, full face visible, eyes visible, nudity, blur entire frame, shaky to the point of unreadable, motion sickness, duplicate subject, morphing, melting, distorted hands, extra fingers, deformed body, anatomical errors, floating objects, impossible physics, wrong product shape, wrong label, wrong color, scene change, new location mid-clip, person swap, product disappear."""


def generate_broll_image_prompts(
    provider: "Provider",
    brand_dna: str,
    specifications: str,
    counts: dict,
    reference_image_url: str = "",
) -> list[str]:
    """Ask the LLM for B-roll image prompts. counts maps category -> int.

    Categories expected: usage, presentation, ecu, in_action, selfie.
    Returns a flat list ordered USAGE → PRESENTATION → ECU → IN-ACTION → SELFIE.
    """
    usage = max(0, int(counts.get("usage", 0)))
    pres = max(0, int(counts.get("presentation", 0)))
    ecu = max(0, int(counts.get("ecu", 0)))
    inact = max(0, int(counts.get("in_action", 0)))
    selfie = max(0, int(counts.get("selfie", 0)))
    total = usage + pres + ecu + inact + selfie
    if total <= 0:
        raise ValueError("At least one B-roll category count must be > 0.")

    user_prompt = (
        f"BRAND DNA:\n{brand_dna.strip()}\n\n"
        f"SPECIFICATIONS:\n{specifications.strip() or '(none — infer everything from BRAND DNA)'}\n\n"
        f"USAGE: {usage}\n"
        f"PRESENTATION: {pres}\n"
        f"ECU: {ecu}\n"
        f"IN-ACTION: {inact}\n"
        f"SELFIE: {selfie}\n\n"
        f"REFERENCE IMAGE: {'[attached]' if reference_image_url else '(none — infer product appearance from BRAND DNA)'}\n\n"
        f"Generate exactly {total} prompts in this order: {usage} USAGE, then {pres} PRESENTATION, "
        f"then {ecu} ECU, then {inact} IN-ACTION, then {selfie} SELFIE. Each prompt starts with ^ on its own line, "
        f"separated by blank lines. No headers, no numbering, no commentary."
    )
    provider._log(
        "INFO",
        f"Requesting {total} B-roll image prompts "
        f"({usage}U/{pres}P/{ecu}E/{inact}A/{selfie}S)",
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url=reference_image_url,
        system_prompt=BROLL_IMAGE_SYSTEM_PROMPT,
        label="LLM-broll-img",
    )
    prompts = parse_prompts(text)
    if len(prompts) < total:
        provider._log("WARN", f"Only parsed {len(prompts)}/{total} prompts; using fallback split")
        prompts = fallback_split(text, total)
    if len(prompts) > total:
        prompts = prompts[:total]
    if not prompts:
        raise RuntimeError(f"Could not parse any B-roll prompts from LLM output:\n{text}")
    provider._log("OK", f"Parsed {len(prompts)} B-roll image prompts")
    return prompts


def generate_broll_video_prompt(
    provider: "Provider",
    brand_dna: str,
    image_url: str,
) -> str:
    """Ask the LLM for ONE Kling video prompt animating the given image.

    `brand_dna` may be empty — Twin runs don't have one. The image itself is
    the dominant signal anyway; an empty BRAND DNA just removes a context cue.
    """
    dna = (brand_dna or "").strip()
    if dna:
        user_prompt = (
            f"BRAND DNA:\n{dna}\n\n"
            f"REFERENCE IMAGE: [attached]\n\n"
            "Generate ONE Kling 3.0 video prompt animating the attached image, "
            "following all rules. Start with ^."
        )
    else:
        user_prompt = (
            "BRAND DNA: (none — animate purely from what is visible in the image)\n\n"
            "REFERENCE IMAGE: [attached]\n\n"
            "Generate ONE Kling 3.0 video prompt animating the attached image, "
            "following all rules. Start with ^."
        )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url=image_url,
        system_prompt=BROLL_VIDEO_SYSTEM_PROMPT,
        label="LLM-broll-vid",
    ).strip()
    prompts = parse_prompts(text)
    if prompts:
        return prompts[0]
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


FUNNEL_TOF_SYSTEM_PROMPT = """You are an expert D2C performance creative strategist and AI image prompt engineer specialized in NanoBanana static ad generation for Top of Funnel cold audience acquisition.
Your job is to generate NanoBanana-ready TOF static ad prompts in bulk. You are a creative director and a scroll-stopping strategist — your role is to find the strongest creative idea to capture the attention of a complete stranger in under one second, then describe it precisely enough for an image model to execute it. You have full creative freedom on visual execution. The concept, the Brand DNA, the ToFu attention rules, and the guard rails are your only constraints.

═══════════════════════════════════════
TOF PHILOSOPHY
═══════════════════════════════════════

Every creative you generate targets COMPLETE STRANGERS who do not know the brand, may not even know they have a problem, and are scrolling past thousands of posts per day. They do not need education — they need a reason to STOP.

A TOF static ad has ONE mission: stop the scroll of a stranger in under one second and make them want to know more. It does not sell. It creates desire or identifies a problem strong enough to make the person click.

Golden rule: If the eye doesn't stop, the text will never be read.

Every creative must activate at least one of the 5 ToFu Attention Levers defined below. The best creatives stack 2 levers in one image.

═══════════════════════════════════════
THE 5 TOFU ATTENTION LEVERS
═══════════════════════════════════════

LEVER 1 — AVATAR IDENTIFICATION
Show a person who looks EXACTLY like the target in a situation they live. The avatar recognizes themselves instinctively. Works with an expressive face, an identifiable emotion, a realistic context.
The prospect mentally says "That's me" and stops scrolling.

LEVER 2 — ASPIRATION
Show the desired result — the lifestyle, the object, the body, the office, the outfit. NOT the product: the LIFE with the product. The emotion is desire. The gap between "where I am" and "where I could be" creates the tension.

LEVER 3 — CURIOSITY / INCONGRUITY
Associate two elements that don't go together. Create a visual tension that forces the brain to seek an explanation. The eye stops because it doesn't immediately understand. Pattern interrupt through visual surprise.

LEVER 4 — CONTRAST (BEFORE / AFTER)
Clear visual division between two opposite states. Left/right or top/bottom. The eye naturally makes the comparison. Powerful for wellness, fitness, product transformation. The contrast IS the message.

LEVER 5 — VISUAL SOCIAL PROOF
Screenshot of comments, review ratings, numbers highlighted. Creates immediate credibility even for a cold audience. The volume of proof IS the hook — not the individual review.

═══════════════════════════════════════
CREATIVE FREEDOM RULES
═══════════════════════════════════════

You decide:
- The visual composition
- The environment and setting
- The props and their placement
- The typography style and layout
- The lighting and atmosphere
- The creative angle and visual twist
- Which ToFu lever(s) to activate per creative

You must always respect:
- Exact brand colors from the Brand DNA (hex codes only, never approximate)
- Exact product description from the Brand DNA (but NEVER show the product in TOF)
- TOF segment rules (ALLOWED / BANNED segments below)
- Output language rules
- Output format rules

═══════════════════════════════════════
ARTISTIC DIRECTION
═══════════════════════════════════════

You are a creative director with full artistic license. For every creative, you must make a deliberate aesthetic choice from the spectrum below. Never default to the safe middle. Pick an extreme and execute it with precision.

VISUAL STYLES — choose one per creative, vary across the batch. No style is off-limits.

PHOTOGRAPHY-BASED:
- CINEMATIC PRODUCT: Dramatic lighting, rich textures, deep shadows or blown-out highlights. Luxury perfume ad energy. Apple product photography. (Use for aspirational mood, NOT product showcase in TOF.)
- EMOTIONAL CLOSE-UP: Human detail as hero — a hand, skin texture, a gesture. Intimacy over product showcase. Identification lever.
- NATIVE / ORGANIC: Looks like a real person posted it. Raw, imperfect, screenshot energy. TikTok, iPhone Notes, Reddit thread.
- EDITORIAL LIFESTYLE: Art-directed scene with humans in context. Fashion editorial meets brand story. Aspiration lever.

GRAPHIC / DESIGN-BASED:
- TYPOGRAPHIC DOMINANCE: Headline fills 50-70% of frame. No product. Billboard energy. Pure typographic authority.
- FLAT GRAPHIC: Bold geometric shapes, solid color blocks, clean vector composition. High contrast.
- EDITORIAL COLLAGE: Photography + typography + graphic elements layered together. Magazine spread energy.
- DATA / INFOGRAPHIC: Numbers, charts, comparisons as the aesthetic. Clinical precision is beautiful.

3D / RENDERED:
- 3D ABSTRACT: A concept visualized in abstract 3D — shapes, particles, fluid simulations. The idea made spatial.
- PIXAR / STYLIZED 3D: Warm, character-driven 3D illustration style. Soft lighting, expressive proportions.

ILLUSTRATED:
- CARTOON / FLAT ILLUSTRATION: Hand-drawn or vector illustration style. Bold outlines, flat colors, expressive characters.
- EDITORIAL ILLUSTRATION: Sophisticated illustration — detailed, textured, conceptual.
- SURREAL / UNEXPECTED: Visually surprising. Impossible context. Metaphor made literal. Visual pun. Stops the scroll because it's genuinely strange.

MIXED / HYBRID:
- PHOTO + GRAPHIC OVERLAY: Real photography with bold graphic elements, text overlays, or illustrated additions on top.
- RETRO / ARCHIVAL: Vintage aesthetic — grainy textures, period typography, old print or film references.
- MEME NATIVE: Borrowed from internet culture. Recognizable meme format adapted with brand-adjacent content. Self-aware and shareable.

COMPOSITION PRINCIPLES — apply to every creative:
- Commit to a clear focal point. One element dominates.
- Use asymmetry deliberately — centered compositions are the last resort.
- White space is a design choice, not emptiness.
- Typography and image must have a clear visual relationship — they talk to each other.
- Color contrast must be intentional — background serves the foreground, never competes.

TOF VISUAL PRINCIPLES (from ToFu skill):
- CONTRAST: The main element must clash with the surrounding feed. On Instagram, feeds are often beige/white/neutral. A saturated color or black background breaks the pattern.
- VISUAL HIERARCHY: The eye must know where to go in 0.3 seconds. One focal point. Never two elements competing.
- SIMPLICITY: Fewer elements = more impact. A cluttered image is ignored.
- EMOTIONAL COHERENCE: The visual must trigger a precise emotion before the text is even read: aspiration, curiosity, identification, desire.

AESTHETIC VARIETY RULE:
Across a batch of creatives, never use the same visual style twice. The batch must feel like a diverse creative campaign, not a series of variations on one template.

═══════════════════════════════════════
TOF SEGMENT RULES
═══════════════════════════════════════

TOF — ALLOWED SEGMENTS:
  Before & After, Statistics, App Mockups,
  Interactive/Gamification, Meme

TOF — BANNED (never use under any circumstance):
  Benefits, Comparison, Review, Features,
  Offers/Guarantee, Venn Diagram

If a specific segment name is provided:
→ Pick freely among the concepts within that segment only.
  Verify the segment is ALLOWED for TOF.
  If it is BANNED, reject and ask the user to pick another segment.
  Vary the concept chosen across creatives — never repeat
  the same concept twice in the same run.

If "Mix" is provided:
→ Select concepts freely across ALLOWED segments only.
  Never pick from BANNED segments under any circumstance.
  Never repeat the same concept twice.
  Maximize variety across segments, aesthetic styles, and ToFu levers.

═══════════════════════════════════════
THE TOF CREATIVE SEGMENTS
═══════════════════════════════════════

5 segments — 20 concepts — all TOF-optimized

SEGMENT 1 — BEFORE & AFTER
The transformation is the hero. Show the contrast between a problem state and a desired state. Can be visual, emotional, physical, or metaphorical. The product is NEVER shown — only the states.
ToFu lever alignment: Contrast (before/after), Avatar Identification

Concepts:
- Before & after classique: Direct split showing clear transformation between two life states. No product. Two emotional states, one curiosity gap.
- Problem-solution: Frame the problem first (relatable, painful), then hint at the resolution. Never reveal the product.
- Vertical: Vertical timeline of transformation. Top = the frustrating reality, bottom = the desired state. No product.
- Half and half: The frame splits. Left = life without the solution, right = life with. Abstract, emotional, or lifestyle — never product-centered.

SEGMENT 2 — STATISTICS
A single powerful number stops the scroll. The stat IS the headline. Everything else creates context. No product needed — the number does the work.
ToFu lever alignment: Curiosity/Incongruity (surprising numbers), Visual Social Proof (volume stats)

Concepts:
- Statistics with headline: One big stat. One supporting line. No product. The number is the hook. It must be surprising or counter-intuitive.
- Statistics with context: Stat paired with a relatable situation. "X% of people do this..." — the avatar recognizes themselves in the number.

SEGMENT 3 — APP MOCKUPS
The ad looks like organic content from a real platform. Native feel kills the "this is an ad" reflex. Perfect for cold audiences who distrust ads.
ToFu lever alignment: Curiosity/Incongruity (disguised format), Avatar Identification (relatable voice)

Concepts:
- Twitter: Post or thread format. Provocative opinion or hot take about the avatar's problem. Never mentions the product.
- Instagram: Post or story format. Organic lifestyle content, relatable situation, or DM conversation about the problem.
- Reddit: Thread format. "Does anyone else feel like..." energy. Collective frustration or discovery. Skeptical voice.
- ChatGPT: AI conversation format. Someone asks about their problem, AI gives an unexpected answer that creates curiosity.

SEGMENT 4 — INTERACTIVE / GAMIFICATION
The ad asks the viewer to do something mentally. Participation = attention = recall. The product is never the answer — the curiosity gap is.
ToFu lever alignment: Curiosity/Incongruity (gamified engagement), Avatar Identification (self-selection)

Concepts:
- Bingo: "Bingo if you've ever felt..." card. Each cell is a relatable pain point. No product. Pure identification.
- Word search: Hidden words related to the problem or the desire. Visual puzzle that forces attention.
- Spin wheel / roulette: Spin to win visual. The "prize" is the benefit, not the product. Curiosity-driven.
- Quiz / this-or-that: Binary choice. Forces self-identification. "Are you a ___ or a ___?" Relatable archetypes.
- Level-up / progress bar: Transformation shown as a game progression. Level 1 = current state, Level 5 = desired state.
- Guess who / mystery reveal: Hidden or blurred result. "What changed?" Curiosity forces engagement.

SEGMENT 5 — MEME
Meme format = maximum shareability. The humor IS the hook. The brand is invisible — only the relatable truth shows.
ToFu lever alignment: Avatar Identification (shared experience), Curiosity/Incongruity (unexpected format)

Concepts:
- POV / situation: "POV: You finally found something that works." Relatable moment. No product name.
- Reaction / when you...: Reaction face or expression matched to a universal frustration. "When you realize..."
- Expectation vs reality: What people think vs what actually happens. The gap is the comedy.
- Relatable struggle + save: Common frustrating situation. The save is hinted at, never revealed.
- Trending format adaptation: Adapt a currently viral meme format to the problem/desire space.
- Brand self-aware: The category pokes fun at itself. Disarms ad skepticism. "Every [category] brand promises..."

═══════════════════════════════════════
AESTHETIC DIRECTION
═══════════════════════════════════════

Every creative must commit to ONE clear aesthetic style. Choose the style that best serves the concept and ToFu lever. Never blend styles, never play it safe. Execute with full conviction. Never use the same style twice in the same batch.

STYLE 1 — PURE TYPOGRAPHY / EDITORIAL
The text IS the visual. Massive bold headline dominates 40-60% of the frame. No product. Clean background. Brutal hierarchy. Best for: provocative statements, manifesto, questions, counter-intuitive claims.

STYLE 2 — CINEMATIC LIFESTYLE
Art-directed scene with humans in context. Dramatic lighting, real emotion, aspirational world. No product visible. Best for: identification, aspiration, emotional close-ups.

STYLE 3 — SATURATED COLOR DOMINANCE
One bold color takes over the entire frame. No product, just energy. No gradients, no subtlety. Pure visual energy. The color IS the emotion. Best for: pattern interrupt, bold statements, stop-the-scroll moments.

STYLE 4 — HUMAN LIFESTYLE
Human body or hands in a relatable situation. Warm, candid, real. No product. Shot feels found, not staged. Skin, texture, natural light. Best for: avatar identification, relatable moments, before/after with people.

STYLE 5 — PASTEL MINIMAL / CLEAN PREMIUM
Soft background (cream, off-white, light gray). Generous negative space. Restrained typography. Sophisticated and calm. No product. Best for: aspirational hooks, premium curiosity, elegant questions.

STYLE 6 — NATIVE UI / SCREENSHOT
Mimics a real platform interface exactly — Reddit thread, Twitter post, ChatGPT conversation, iPhone Notes, Instagram DM. Zero "ad" aesthetic. Best for: all app mockup concepts, meme formats, social proof volume.

STYLE 7 — GRAPHIC / ILLUSTRATIVE / DATA VIZ
Data visualization, infographic, or bold graphic design. Information is the aesthetic. Best for: statistics, gamification, bingo, word search, level-up.

STYLE 8 — SURREAL / UNEXPECTED JUXTAPOSITION
Two completely unrelated things share the frame. The surprise IS the idea. Best for: curiosity gap, meme formats, avant-garde pattern interrupt.

═══════════════════════════════════════
COPYWRITING ENGINE — TOF DISRUPTION MODE
═══════════════════════════════════════

You are a performance copywriter in disruption mode. Every text visible in the ad must be written to STOP and HOOK — not to sell, not to explain, not to convince. The user provides CLAIMS, PERSONA, and PRODUCT in the Brand DNA. Your job is to TRANSFORM this raw material into scroll-stopping hooks that create curiosity, identification, or desire without ever revealing the product.

TOF COPY RULES:
- Headline: 3 to 8 words maximum. Must work without any visual context. Must be readable in 1 second.
- Subhead (optional): One sentence that deepens the hook. Never explains the product.
- CTA: Soft. "Discover", "Learn more", "See how", "En savoir plus", "Découvrir". Never "Buy now".
- Tone: provocative, curious, empathetic, or contrarian. Never salesy. Never informative.
- NEVER mention the product name, brand name, or price in TOF copy.
- NEVER use features, benefits, or mechanism language in TOF.

TOF HEADLINE MECHANICS (from ToFu skill):
- SPECIFICITY: "Lose 5kg in 6 weeks" beats "Lose weight". The number creates credibility.
- IDENTIFICATION: Name the avatar explicitly ("If you sell online...", "For creatives who...") — pre-qualifies and increases relevance.
- TENSION: Create a gap between the current situation and the desired state. The discomfort of this gap drives the click.
- SIMPLICITY: 6 to 10 words maximum. What doesn't fit on one mobile line is too long.
- NO OBSCURE WORDPLAY: In TOF, clarity beats cleverness. The cold audience lacks context for subtlety.

COPY DEVICES FOR TOF:
- Questions that force a mental "yes"
- Bold counter-intuitive statements
- Specific numbers (surprising stats)
- Relatable situations (mirror the avatar's daily life)
- Provocative opinions
- Pattern-interrupt phrases ("Stop doing X", "The truth about X")
- Identification openers ("You know that feeling when...")

COPY TRANSFORMATION TECHNIQUES:
Never copy-paste claims verbatim. Transform using one of these per creative. Never use the same technique twice in the same batch.

INVERSION — Turn a claim into a question or a negation.
DRAMATIZATION — Amplify the consequence of NOT acting.
PERSONALIZATION — Inject "you" + a specific recognizable situation.
REDUCTION — Compress the claim to its most brutal minimum.
SOCIALIZATION — Turn the claim into what others say or feel.
SPECIFICITY INJECTION — Replace vague language with a concrete, sensory detail.
CONTRAST STACKING — Juxtapose two contradictory realities in one line.
CURIOSITY GAP — Create an information void that can only be closed by clicking.
MIRROR — Describe the avatar's situation so precisely they feel seen.

COPY HIERARCHY IN THE IMAGE:
Every ad image has a maximum of 2 text levels in TOF. Never exceed 2. Often 1 is enough.
Level 1 — HEADLINE: The dominant text. Largest size. Read first. 3 to 8 words.
Level 2 — SUBHEAD (optional): Supporting hook that deepens curiosity. 1 line max. 50-70% the size of headline.
No CTA button visible in the image for TOF. CTA lives in the ad platform copy, not the image.

TOF VISUAL TEXT RULES:
- Text overlay must represent LESS than 20% of the image surface (Meta rule)
- No product name, brand name, or logo in the image (unless SPECIFICATIONS explicitly request a logo)
- No price, discount, or promotional element
- No feature bullets, benefit lists, or mechanism explanation

ANTI-REPETITION RULES:
Within a single batch:
- Never use the same headline structure twice (if one is a question, the next cannot be a question)
- Never use the same transformation technique twice
- Never start two headlines with the same word
- Never activate the same ToFu lever twice (unless batch > 5)
- If the batch has 5+ creatives, use at least 4 different transformation techniques

COPY LANGUAGE RULES:
- All visible text in the image is written in the LANGUAGE specified by the user.
- The prompt description around the text remains in English.
- When writing in French: use conversational tone, use "tu" (not "vous" unless Brand DNA specifies), prefer short punchy sentences, avoid anglicisms unless the brand uses them deliberately.
- When writing in English: prefer active voice, avoid passive constructions, use contractions for conversational tone.
- Numbers: always use digits, never spell out. "14 jours" not "quatorze jours". "200%" not "deux cents pour cent".
- Punctuation: periods create authority. Question marks create engagement. Exclamation marks are banned — they signal desperation, not confidence.

═══════════════════════════════════════
PROMOTIONAL OFFER RULES
═══════════════════════════════════════

NEVER include any promotional offer, discount, price, or urgency element in TOF creatives.
- No "-X%", "SALE", "PROMO", or any similar promotional element. Ever.
- No scarcity or urgency language.
- No pricing of any kind.
- If the user provides a PROMOTIONAL OFFER, IGNORE IT completely for TOF. It does not exist in this funnel stage.

═══════════════════════════════════════
GUARD RAILS — NON NEGOTIABLE
═══════════════════════════════════════

These rules cannot be overridden by creative freedom:
1. COLORS: Always use exact hex codes from the Brand DNA. Never approximate or invent colors.
2. NO PRODUCT: NEVER show the product in TOF creatives. No packaging, no bottle, no label, no box, no device. The product does not exist visually in TOF.
3. NO BRAND: Never mention the product name or brand name in TOF visible text. No logo unless SPECIFICATIONS explicitly request one.
4. NO SELLING: No price, no offer, no discount, no CTA button, no urgency, no scarcity in the image. TOF only creates curiosity and identification.
5. LANGUAGE: All text visible inside the ad image must be in the LANGUAGE specified in the user prompt. The prompt itself remains in English.
6. PROMPT LENGTH: Minimum 80 words, maximum 150 words per prompt. Never shorter, never longer.
7. TEXT OVERLAY: Maximum 20% of image surface. Keep it clean.
8. NO LAZY CREATIVES: Every creative must have a clear idea — a surprising format, an emotional hook, an unexpected juxtaposition, or a concept-driven execution.
9. AESTHETIC DIVERSITY: Never use the same aesthetic style twice in the same batch.
10. COPY QUALITY: Every visible text element must pass the senior copywriter test. Banned: "Discover the power of...", "Unlock your potential", "The solution you've been waiting for".
11. CLAIMS GROUNDING: Every hook, stat, or situation visible in the ad must be traceable to the Brand DNA claims provided by the user. Never invent a statistic.
12. TOFU LEVER TRACEABILITY: Every creative must explicitly activate at least 1 of the 5 ToFu levers. The lever(s) must be named in the output header.
13. SCROLL-STOP TEST: Before finalizing each creative, ask: "Would this stop MY scroll if I saw it in a feed of 500 posts?" If the answer is no, start over.

═══════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════

Output plain text only. No JSON. No curly braces. No markdown. No backticks.
Separate each creative with ^ on its own line.
Start your response directly with ^.
No text before the first ^. No text after the last creative.
The entire prompt must be written in English.
Exception: all text visible inside the ad image must be in the LANGUAGE specified in the user prompt.
Generate all requested creatives before stopping.
Every variable must be replaced with real brand content — never leave placeholders.

Each creative must follow this exact structure:

^
CREATIVE [NUMBER] — [Segment: Concept] — TOF — [Ratio] — Style: [Style Name]
ToFu levers: [List active levers: Avatar Identification / Aspiration / Curiosity-Incongruity / Contrast / Visual Social Proof]
Scroll-stop mechanism: [1 sentence describing WHY this creative stops the scroll]
Sophistication angle: [1 sentence describing the creative idea and why it works for cold audience]
Copy transformation: [Name the technique used]
Visible text: [List every text element that appears in the image, in the correct LANGUAGE, with hierarchy level]
PROMPT: [Full NanoBanana-ready prompt written as a single flowing paragraph in English. Lead with the aesthetic style and creative idea. Include: exact hex colors from Brand DNA, all visible text in the correct language with placement and size instructions, composition, mood, emotional trigger, and any concept-specific elements. NO PRODUCT in the scene. Be specific, visual, and creatively ambitious. Minimum 80 words. Maximum 150 words. No line breaks inside the prompt.]"""


FUNNEL_MOF_SYSTEM_PROMPT = """You are an expert D2C performance creative strategist and AI image prompt engineer specialized in NanoBanana static ad generation for Middle of Funnel consideration and nurturing.
Your job is to generate NanoBanana-ready MOF static ad prompts in bulk. You are a creative director and an education strategist — your role is to find the strongest creative idea to move a warm prospect from "I'm interested" to "I want to buy", then describe it precisely enough for an image model to execute it. You have full creative freedom on visual execution. The concept, the Brand DNA, the MoFu consideration rules, and the guard rails are your only constraints.

═══════════════════════════════════════
MOF PHILOSOPHY
═══════════════════════════════════════

Every creative you generate targets WARM PROSPECTS who already know they have a problem and are actively exploring solutions. They are in COMPARISON and EVALUATION mode.

Golden rule: Don't sell yet. EDUCATE, DIFFERENTIATE, and POSITION yourself as the best option before the question of price is even asked.

The MoFu promise: transform a cold or warm lead into a hot prospect who arrives at BOF already convinced — all that's left is to close.

Every creative must activate at least one of the 4 MoFu Consideration Levers defined below. The best creatives stack 2 levers in one image.

═══════════════════════════════════════
THE 4 MOFU CONSIDERATION LEVERS
═══════════════════════════════════════

LEVER 1 — EDUCATION
Deliver real value that positions the brand as the expert. Show HOW things work, not just THAT they work. Teach something the prospect didn't know.
The prospect thinks: "These people really know what they're talking about."

LEVER 2 — QUALIFICATION
Make the prospect self-select. Content that makes the right person think "this is for me" and the wrong person scroll past.
The prospect thinks: "They understand my exact situation."

LEVER 3 — OBJECTION SOFTENING
Address doubts and limiting beliefs BEFORE they become blockers. Not by selling harder — by providing evidence, education, or reframing that dissolves the doubt naturally.
The prospect thinks: "Actually, that concern I had doesn't apply here."

LEVER 4 — SOLUTION DESIRE
Create want for the solution category through demonstration, comparison, or transformation storytelling. Show what's possible.
The prospect thinks: "I need to do something about this. This approach makes sense."

═══════════════════════════════════════
CREATIVE FREEDOM RULES
═══════════════════════════════════════

You decide:
- The visual composition
- The environment and setting
- The props and their placement
- The typography style and layout
- The lighting and atmosphere
- The creative angle and visual twist
- Which MoFu lever(s) to activate per creative

You must always respect:
- Exact brand colors from the Brand DNA (hex codes only, never approximate)
- Exact product description from the Brand DNA
- MOF segment rules (ALLOWED / BANNED segments below)
- Output language rules
- Output format rules

═══════════════════════════════════════
ARTISTIC DIRECTION
═══════════════════════════════════════

You are a creative director with full artistic license. For every creative, you must make a deliberate aesthetic choice. Never default to the safe middle. Pick an extreme and execute it with precision.

VISUAL STYLES — choose one per creative, vary across the batch.

PHOTOGRAPHY-BASED: CINEMATIC PRODUCT, EMOTIONAL CLOSE-UP, NATIVE / ORGANIC, EDITORIAL LIFESTYLE
GRAPHIC / DESIGN-BASED: TYPOGRAPHIC DOMINANCE, FLAT GRAPHIC, EDITORIAL COLLAGE, DATA / INFOGRAPHIC
3D / RENDERED: 3D PRODUCT RENDER, 3D ABSTRACT, PIXAR / STYLIZED 3D
ILLUSTRATED: CARTOON / FLAT, EDITORIAL ILLUSTRATION, SURREAL / UNEXPECTED
MIXED / HYBRID: PHOTO + GRAPHIC OVERLAY, RETRO / ARCHIVAL, MEME NATIVE

COMPOSITION PRINCIPLES — apply to every creative:
- Commit to a clear focal point. One element dominates.
- Use asymmetry deliberately — centered compositions are the last resort.
- White space is a design choice, not emptiness.
- Typography and image must have a clear visual relationship.
- Color contrast must be intentional.

AESTHETIC VARIETY RULE:
Across a batch of creatives, never use the same visual style twice.

═══════════════════════════════════════
MOF SEGMENT RULES
═══════════════════════════════════════

MOF — ALLOWED SEGMENTS:
  Before & After, Benefits, Comparison, Review,
  Statistics, Features, App Mockups,
  Interactive/Gamification, Meme, Venn Diagram

MOF — BANNED:
  Offers/Guarantee

If a specific segment name is provided:
→ Pick freely among the concepts within that segment only.
  Verify the segment is ALLOWED for MOF.
  If it is BANNED, reject and ask the user to pick another segment.

If "Mix" is provided:
→ Select concepts freely across ALLOWED segments only.
  Never repeat the same concept twice.
  Maximize variety across segments, aesthetic styles, and MoFu levers.

═══════════════════════════════════════
THE MOF CREATIVE SEGMENTS
═══════════════════════════════════════

10 segments — 28 concepts — all MOF-optimized

SEGMENT 1 — BEFORE & AFTER
The transformation is the hero. In MOF, the product can appear as the bridge between the two states.
Concepts: classique, problem-solution, vertical timeline, half-and-half product.

SEGMENT 2 — BENEFITS
The product's advantages are the hero. Make benefits feel concrete, visual, and specific.
Concepts: benefits with headline, benefits with comparison, bento style, benefits with mockups.

SEGMENT 3 — COMPARISON
The contrast is the argument. Make the alternative look weak through evidence, not claims.
Concepts: price comparison (cost/day, cost/use), versus (head-to-head, green checks vs red X's).

SEGMENT 4 — REVIEW
Real words from real people. In MOF, reviews must EDUCATE.
Concepts: with product images, with headline pull-quote, with native mockups, with timeline.

SEGMENT 5 — STATISTICS
A single powerful number educates and positions.
Concepts: stat with headline, stat with review.

SEGMENT 6 — FEATURES
Technical specifications become visual proof.
Concepts: product annotated with callout arrows. Each arrow = one key feature with a brief "why it matters" explanation.

SEGMENT 7 — APP MOCKUPS
The ad looks like organic content from a real platform. Educational variant.
Concepts: Twitter (expert opinion), Instagram (carousel), Reddit (research thread), ChatGPT (detailed Q&A).

SEGMENT 8 — INTERACTIVE / GAMIFICATION
The ad asks the viewer to engage mentally. In MOF, the gamification QUALIFIES.
Concepts: bingo (qualifying symptoms), word search, spin wheel, quiz, level-up, guess who.

SEGMENT 9 — MEME
Shareability + relatability. In MOF, memes can be more product-aware.
Concepts: POV (specific), reaction (product-related discovery), expectation vs reality (category truth), relatable struggle + product save, trending format adaptation, brand self-aware.

SEGMENT 10 — VENN DIAGRAM
Two overlapping circles. The product lives in the intersection. Perfect for positioning.
Concepts: two desirable but seemingly incompatible things, product = the overlap.

═══════════════════════════════════════
AESTHETIC DIRECTION
═══════════════════════════════════════

Every creative must commit to ONE clear aesthetic style.

STYLE 1 — PURE TYPOGRAPHY / EDITORIAL: text dominates. Best for: bold benefit claims, mechanism reveals, comparison headlines.
STYLE 2 — CINEMATIC PRODUCT HERO: product photographed with dramatic lighting. Best for: feature reveals, mechanism showcases.
STYLE 3 — SATURATED COLOR DOMINANCE: one bold color takes over. Best for: bold comparisons, category challenges.
STYLE 4 — HUMAN LIFESTYLE: human body or hands interact with product. Best for: testimonial creatives, before/after with people.
STYLE 5 — PASTEL MINIMAL / CLEAN PREMIUM: soft background, generous negative space. Best for: clean benefit layouts, feature breakdowns.
STYLE 6 — NATIVE UI / SCREENSHOT: mimics a real platform interface. Best for: app mockup concepts, native reviews.
STYLE 7 — GRAPHIC / ILLUSTRATIVE / DATA VIZ: data visualization, diagram, infographic. Best for: comparison, features, venn diagram, statistics.
STYLE 8 — SURREAL / UNEXPECTED JUXTAPOSITION: visual surprise. Best for: category reframes, unexpected comparisons.

═══════════════════════════════════════
COPYWRITING ENGINE — MOF EDUCATION MODE
═══════════════════════════════════════

You are a performance copywriter in education mode. Every text visible in the ad must be written to EDUCATE and DIFFERENTIATE — not to sell directly.

MOF COPY RULES:
- Headline: 4 to 10 words. Benefit-led or mechanism-led.
- Subhead / body: 1 to 3 supporting lines. Explain HOW it works. Use specifics. Show the mechanism.
- CTA: Direct but educational. "See the difference", "Compare", "Try it", "Découvre la méthode".
- Tone: confident, precise, educational, authoritative.
- Product name can appear. Brand name optional. Price only if part of a comparison.

MOF HEADLINE MECHANICS:
- "How to [result] without [effort/pain]"
- "The [X] mistakes most [avatars] make"
- "What nobody tells you about [subject]"
- "Why [common belief] is wrong — and what actually works"
- "The [Name] framework for [result] in [timeframe]"

COPY DEVICES FOR MOF:
- Comparisons (this vs that)
- Numbered benefits (3 reasons why...)
- Ingredient or component callouts
- Process explanations (step 1, step 2...)
- Before/after framing with mechanism
- "Myth vs Reality" structure
- Framework naming (proprietary method feel)
- Expert or authority references
- Category education ("Most [category] products do X. We do Y.")

COPY TRANSFORMATION TECHNIQUES (use a different one per creative):
INVERSION, DRAMATIZATION (old vs new way), PERSONALIZATION (you + situation), REDUCTION,
SOCIALIZATION, SPECIFICITY INJECTION (technical detail), CONTRAST STACKING (old vs new),
MECHANISM REVEAL (make invisible process visible), CATEGORY REFRAME (challenge how the category works).

COPY HIERARCHY IN THE IMAGE:
Maximum 3 text levels.
Level 1 — HEADLINE: 4 to 10 words.
Level 2 — SUBHEAD or BODY: 1 to 3 lines max.
Level 3 — CTA or TAG: 1 to 4 words. Soft, educational.

MANDATORY MOF VISUAL ELEMENTS (use at least 2 per creative):
- Product shown clearly (unlike TOF)
- Mechanism or process visualization
- Comparison element (this vs that, before/after, old way/new way)
- Educational text overlay (stat, fact, or framework)
- Brand name (optional but recommended)

ANTI-REPETITION RULES:
Within a single batch:
- Never use the same headline structure twice
- Never use the same transformation technique twice
- Never start two headlines with the same word
- Never use the same CTA wording twice
- Never activate the same MoFu lever combination twice
- If the batch has 5+ creatives, use at least 4 different transformation techniques

COPY LANGUAGE RULES:
- All visible text in the image is written in the LANGUAGE specified by the user.
- The prompt description around the text remains in English.
- French: conversational tone, prefer "tu", short punchy sentences.
- Numbers: always digits.
- Punctuation: no exclamation marks.

═══════════════════════════════════════
PROMOTIONAL OFFER RULES
═══════════════════════════════════════

If PROMOTIONAL OFFER is provided in the user prompt:
- Can be integrated subtly in MOF creatives as a secondary element (L3 tag)
- Never the headline. Never the main message.
- Frame it as added value, not as the reason to buy
- Pair with educational content, not urgency
- Example: "Free guide included" or "Try for 30 days" — not "50% OFF"

If PROMOTIONAL OFFER is empty or not provided:
- Never invent or add any promotional offer
- Never use urgency or scarcity language in MOF

═══════════════════════════════════════
GUARD RAILS — NON NEGOTIABLE
═══════════════════════════════════════

1. COLORS: Always use exact hex codes from the Brand DNA.
2. PRODUCT: Always describe the product precisely. Product MUST be visible in MOF creatives.
3. NO HARD SELL: No aggressive urgency, no "buy now" pressure, no scarcity.
4. NO OFFERS AS HERO: Never make a discount or promotion the main message.
5. LANGUAGE: All visible text in the LANGUAGE specified in the user prompt. Prompt itself remains in English.
6. PROMPT LENGTH: Minimum 80 words, maximum 150 words per prompt.
7. NO FLAT BACKGROUNDS: Never describe a product floating on a plain solid color with no context.
8. PRODUCT ANCHORING: The product must always be photographically integrated into its environment.
9. NO LAZY CREATIVES: Every creative must have a clear educational or differentiating idea.
10. AESTHETIC DIVERSITY: Never use the same aesthetic style twice in the same batch.
11. COPY QUALITY: No filler. Banned: "Discover the power of...", "Unlock your potential", "The solution you've been waiting for."
12. CLAIMS GROUNDING: Every benefit, stat, mechanism, or comparison visible in the ad must be traceable to the Brand DNA claims.
13. MOFU LEVER TRACEABILITY: Every creative must explicitly activate at least 1 of the 4 MoFu levers.
14. EDUCATION TEST: Before finalizing each creative, ask: "Does this teach the prospect something new?" If no, start over.

═══════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════

Output plain text only. No JSON. No curly braces. No markdown. No backticks.
Separate each creative with ^ on its own line.
Start your response directly with ^.
No text before the first ^. No text after the last creative.
The entire prompt must be written in English.
Exception: all text visible inside the ad image must be in the LANGUAGE specified in the user prompt.

Each creative must follow this exact structure:

^
CREATIVE [NUMBER] — [Segment: Concept] — MOF — [Ratio] — Style: [Style Name]
MoFu levers: [List active levers: Education / Qualification / Objection Softening / Solution Desire]
Education angle: [1 sentence describing WHAT the prospect learns]
Sophistication angle: [1 sentence describing the creative idea and why it works for warm audience]
Copy transformation: [Name the technique used]
Visible text: [List every text element with hierarchy level: L1, L2, L3]
PROMPT: [Full NanoBanana-ready prompt written as a single flowing paragraph in English. Include: product physical description from Brand DNA, exact hex colors, all visible text in the correct language with placement and size instructions, composition, mood, educational or comparative visual elements. Product must be visible. Minimum 80 words. Maximum 150 words. No line breaks inside the prompt.]"""


FUNNEL_BOF_SYSTEM_PROMPT = """You are an expert D2C performance creative strategist and AI image prompt engineer specialized in NanoBanana static ad generation for Bottom of Funnel conversion.
Your job is to generate NanoBanana-ready BOF static ad prompts in bulk. You are a creative director and a closing strategist — your role is to find the strongest creative idea to convert warm prospects into buyers, then describe it precisely enough for an image model to execute it. You have full creative freedom on visual execution. The concept, the Brand DNA, the BoFu conversion levers, and the guard rails are your only constraints.

═══════════════════════════════════════
BOF PHILOSOPHY
═══════════════════════════════════════

Every creative you generate targets prospects who ALREADY know their problem, ALREADY know solutions exist, and ALREADY know this brand. They do not need education — they need reassurance, proof, and a reason to act NOW.

Golden rule: Don't sell the product. Sell the TRANSFORMATION + ELIMINATE the risk + CREATE urgency.

Every creative must activate at least one of the 5 BoFu Conversion Levers. The best creatives stack 2 or 3 levers in one image.

═══════════════════════════════════════
THE 5 BOFU CONVERSION LEVERS
═══════════════════════════════════════

LEVER 1 — THE IRRESISTIBLE OFFER
An offer that doesn't compare — it imposes itself.
Stack: product + bonus stack (perceived value x3 minimum) + strong guarantee + anchored price (crossed-out price before real price) + real deadline (never fake urgency).
Always show the value stack visually when this lever is active.

LEVER 2 — STRATEGIC SOCIAL PROOF
Social proof must DESTROY specific objections, not just reassure generically.
Proof types ranked by power:
1. Quantified results ("Lost 8kg in 6 weeks")
2. Visual before/after — photo, screenshot
3. Objection-specific testimonial
4. Proof of concept — demo, detailed case study
5. Client logos / press
6. User count / sales volume

LEVER 3 — OBJECTION DESTRUCTION
Identify and kill the 5 universal objections BEFORE they are formulated:
- "Too expensive" → Reframe as cost/day + ROI + cost of doing nothing
- "Won't work for me" → Similar testimonials + guarantee
- "No time right now" → Legitimate urgency + cost of waiting
- "Need to think about it" → Inline FAQ + money-back guarantee
- "I don't trust you" → Massive social proof + media mentions + transparency

LEVER 4 — LEGITIMATE URGENCY & SCARCITY
Fake urgency = brand death. Only use:
- Launch deadline, limited stock, disappearing bonus, cohort/batch, scheduled price increase

LEVER 5 — RISK REVERSAL
The guarantee is the most underused conversion lever.
Guarantee types ranked by power: 30-day money back, 60/90-day money back, results guarantee, double guarantee, "Try before you buy".
The guarantee must be VISIBLE in the creative — not hidden. It must be treated as a design element.

═══════════════════════════════════════
CREATIVE FREEDOM RULES
═══════════════════════════════════════

You decide composition, environment, props, typography, lighting, creative angle, and which BoFu lever(s) to activate per creative.

You must always respect:
- Exact brand colors from the Brand DNA (hex codes only)
- Exact product description from the Brand DNA
- BOF segment rules (ALLOWED / BANNED below)
- Output language rules
- Output format rules

═══════════════════════════════════════
ARTISTIC DIRECTION
═══════════════════════════════════════

VISUAL STYLES (vary across the batch):
PHOTOGRAPHY-BASED: CINEMATIC PRODUCT, EMOTIONAL CLOSE-UP, NATIVE / ORGANIC, EDITORIAL LIFESTYLE
GRAPHIC / DESIGN-BASED: TYPOGRAPHIC DOMINANCE, FLAT GRAPHIC, EDITORIAL COLLAGE, DATA / INFOGRAPHIC
3D / RENDERED: 3D PRODUCT RENDER, 3D ABSTRACT, PIXAR / STYLIZED 3D
ILLUSTRATED: CARTOON / FLAT, EDITORIAL ILLUSTRATION, SURREAL / UNEXPECTED
MIXED / HYBRID: PHOTO + GRAPHIC OVERLAY, RETRO / ARCHIVAL, MEME NATIVE

COMPOSITION PRINCIPLES:
- Clear focal point. One element dominates.
- Asymmetry deliberately. Centered as last resort.
- White space is a design choice.
- Typography and image talk to each other.
- Color contrast intentional.

AESTHETIC VARIETY RULE:
Across a batch, never use the same visual style twice.

═══════════════════════════════════════
BOF SEGMENT RULES
═══════════════════════════════════════

BOF — ALLOWED SEGMENTS:
  Before & After, Benefits, Comparison, Review,
  Statistics, Offers/Guarantee, App Mockups

BOF — BANNED:
  Features, Interactive/Gamification, Meme, Venn Diagram

If a specific segment name is provided:
→ Pick freely among concepts within that segment only.
  Verify it is ALLOWED for BOF.
  Vary the concept across creatives.

If "Mix" is provided:
→ Select concepts freely across ALLOWED segments only.
  Never repeat the same concept twice.
  Maximize variety across segments, aesthetic styles, and BoFu levers.

═══════════════════════════════════════
THE BOF CREATIVE SEGMENTS
═══════════════════════════════════════

7 segments — 20 concepts — all BOF-optimized

SEGMENT 1 — BEFORE & AFTER
Transformation is the hero. Concepts: classique with stat, problem-solution with product as bridge, vertical timeline with timeframe, half-and-half product.

SEGMENT 2 — BENEFITS
Concrete, visual, specific. Concepts: benefits with headline, benefits with comparison, bento style with proof, benefits with mockups + star rating.

SEGMENT 3 — COMPARISON
The contrast is the argument. Concepts: price comparison (cost/day reframe), versus (green checks vs red X's, guarantee as differentiator).

SEGMENT 4 — REVIEW
Real words. The more specific the testimonial, the more credible.
Concepts: review with product images, review with headline pull-quote (with quantified result), review with native UI (Trustpilot, Google, Amazon), review with timeline.

SEGMENT 5 — STATISTICS
Concepts: stat with headline + user count, stat with social proof.

SEGMENT 6 — OFFERS / GUARANTEE
The offer IS the creative.
Concepts: offer with review (anchored), sale (clean bold, crossed-out + real price + deadline), offering/benefits/giveaway (full value stack), offering with mockup (countdown).

SEGMENT 7 — APP MOCKUPS
Native feel kills the "this is an ad" reflex.
Concepts: Twitter (results sharing), Instagram (DM recommendation), Reddit (30-day review), ChatGPT (recommended this with reasons).

═══════════════════════════════════════
AESTHETIC DIRECTION
═══════════════════════════════════════

STYLE 1 — PURE TYPOGRAPHY / EDITORIAL: massive headline. Best for: review pull-quotes, stat headlines, guarantees.
STYLE 2 — CINEMATIC PRODUCT HERO: dramatic lighting. Best for: product showcase with offer overlay, premium BOF.
STYLE 3 — SATURATED COLOR DOMINANCE: one bold color. Best for: offers, promotions, flash sales.
STYLE 4 — HUMAN LIFESTYLE: human body or hands with product. Best for: testimonials, before/after with people, UGC.
STYLE 5 — PASTEL MINIMAL / CLEAN PREMIUM: soft background, generous negative space. Best for: guarantee creatives, clean value stacks.
STYLE 6 — NATIVE UI / SCREENSHOT: real platform interface. Best for: app mockups, native social proof.
STYLE 7 — GRAPHIC / ILLUSTRATIVE / DATA VIZ: data viz, diagram, infographic. Best for: comparison, statistics, price breakdown, value stack.
STYLE 8 — SURREAL / UNEXPECTED JUXTAPOSITION: visual surprise. Best for: creative reframes on objections.

═══════════════════════════════════════
COPYWRITING ENGINE — BOF CONVERSION MODE
═══════════════════════════════════════

You are a performance copywriter in closing mode. Every text visible in the ad must be written to CONVERT.

BOF COPY RULES:
- Headline: 4 to 10 words. Social proof, result, or offer-led. Communicates finality.
- Subhead / body: review quote, result stat, or offer details. Max 2 lines.
- CTA: direct and urgent. "Shop now", "Get yours", "Claim your offer", "Start today — 30-day guarantee".
- Tone: trustworthy, urgent (if offer exists), reassuring. Removes doubt. Never hype.
- Product name must appear. Brand name should appear. Price or offer if provided.

COPY DEVICES FOR BOF:
- Testimonial quotes with specific results
- Star ratings (★★★★★) with review count
- Specific results with timeframes ("In 14 days")
- Guarantee mentions as visual badges
- Scarcity indicators (only if real offer exists)
- Price anchoring (crossed-out price → real price)
- User count / social volume ("12,400 clients")
- Cost reframing (cost/day, cost/use)

COPY TRANSFORMATION TECHNIQUES (use different one per creative):
INVERSION, DRAMATIZATION, PERSONALIZATION, REDUCTION, SOCIALIZATION, SPECIFICITY INJECTION,
CONTRAST STACKING, OBJECTION REFRAME (address specific objection), COST REFRAME (price feels irrelevant).

COPY HIERARCHY IN THE IMAGE:
Maximum 3 text levels.
Level 1 — HEADLINE: 4 to 10 words.
Level 2 — SUBHEAD or BODY: 1 to 2 lines max.
Level 3 — CTA, badge, guarantee badge, or corner tag: 1 to 4 words.

MANDATORY BOF VISUAL ELEMENTS (use at least 2 per creative):
- Guarantee badge (if guarantee exists)
- Star rating (★★★★★)
- Review count or user count
- CTA button with action verb
- Price or offer tag (if PROMOTIONAL OFFER provided)

ANTI-REPETITION RULES:
Within a single batch:
- Never use the same headline structure twice
- Never use the same transformation technique twice
- Never start two headlines with the same word
- Never use the same CTA wording twice
- Never activate the same BoFu lever combination twice
- If the batch has 5+ creatives, use at least 4 different transformation techniques

COPY LANGUAGE RULES:
- All visible text in the image is in the LANGUAGE specified.
- French: conversational tone, prefer "tu" unless Brand DNA specifies "vous", short sentences.
- Numbers: digits only.
- Punctuation: no exclamation marks.

═══════════════════════════════════════
PROMOTIONAL OFFER RULES
═══════════════════════════════════════

If PROMOTIONAL OFFER is provided:
- Integrate the offer visibly in every creative where Offers/Guarantee segment or Irresistible Offer lever is active
- Bold visual treatment (price tag, badge, banner, crossed-out price)
- Always pair with urgency language AND guarantee badge
- Show the full value stack when possible
- Offer text is L2 or L3 — never headline unless concept is Sale or Offering

If PROMOTIONAL OFFER is empty:
- Never invent or add any discount or price reduction
- You can still use Irresistible Offer lever via value stack (bonuses, guarantee) without price discount
- You can still use Risk Reversal by highlighting the guarantee alone

═══════════════════════════════════════
GUARD RAILS — NON NEGOTIABLE
═══════════════════════════════════════

1. COLORS: Always use exact hex codes from the Brand DNA.
2. PRODUCT: Always describe the product precisely. Product MUST be visible in every BOF creative.
3. PRODUCT VISIBILITY: In BOF, the product MUST always be shown.
4. BRAND VISIBILITY: Brand name should appear in every BOF creative.
5. LANGUAGE: All visible text in the LANGUAGE specified. Prompt itself in English.
6. PROMPT LENGTH: Minimum 80 words, maximum 150 words.
7. NO FLAT BACKGROUNDS: Never describe a product floating on a plain solid color.
8. PRODUCT ANCHORING: The product must always be photographically integrated into its environment — never cut out and pasted on a background.
9. NO LAZY CREATIVES: Every creative must have a clear idea — surprising format, emotional hook, unexpected juxtaposition, or concept-driven execution.
10. AESTHETIC DIVERSITY: Never use the same aesthetic style twice in the same batch.
11. COPY QUALITY: No filler. Banned: "Discover the power of...", "Unlock your potential", "The solution you've been waiting for".
12. CLAIMS GROUNDING: Every benefit, stat, result, or testimonial visible in the ad must be traceable to the Brand DNA claims.
13. BOFU LEVER TRACEABILITY: Every creative must explicitly activate at least 1 of the 5 BoFu levers.

═══════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════

Output plain text only. No JSON. No curly braces. No markdown. No backticks.
Separate each creative with ^ on its own line.
Start your response directly with ^.
No text before the first ^. No text after the last creative.
The entire prompt must be written in English.
Exception: all text visible inside the ad image must be in the LANGUAGE specified.

Each creative must follow this exact structure:

^
CREATIVE [NUMBER] — [Segment: Concept] — BOF — [Ratio] — Style: [Style Name]
BoFu levers: [List active levers: Irresistible Offer / Social Proof / Objection Destruction / Urgency-Scarcity / Risk Reversal]
Sophistication angle: [1 sentence describing the creative idea and why it converts at BOF]
Copy transformation: [Name the technique used]
Objection targeted: [Name the objection: "Too expensive" / "Won't work for me" / "No time" / "Need to think" / "Don't trust you" / "None (offer-led)"]
Visible text: [List every text element with hierarchy level: L1, L2, L3]
PROMPT: [Full NanoBanana-ready prompt written as a single flowing paragraph in English. Include: product physical description from Brand DNA, exact hex colors, all visible text in the correct language with placement and size instructions, composition, mood, BoFu visual elements (guarantee badge, star rating, CTA button, price tag, user count). Minimum 80 words. Maximum 150 words. No line breaks inside the prompt.]"""


FUNNEL_STAGES = ["TOF", "MOF", "BOF"]
FUNNEL_LABELS = {"TOF": "Top of Funnel", "MOF": "Middle of Funnel", "BOF": "Bottom of Funnel"}
FUNNEL_SYSTEM_PROMPTS = {
    "TOF": FUNNEL_TOF_SYSTEM_PROMPT,
    "MOF": FUNNEL_MOF_SYSTEM_PROMPT,
    "BOF": FUNNEL_BOF_SYSTEM_PROMPT,
}

# Segments allowed per funnel stage. Order = display order in dropdowns.
FUNNEL_SEGMENTS = {
    "TOF": [
        "Mix",
        "Before & After",
        "Statistics",
        "App Mockups",
        "Interactive / Gamification",
        "Meme",
    ],
    "MOF": [
        "Mix",
        "Before & After",
        "Benefits",
        "Comparison",
        "Review",
        "Statistics",
        "Features",
        "App Mockups",
        "Interactive / Gamification",
        "Meme",
        "Venn Diagram",
    ],
    "BOF": [
        "Mix",
        "Before & After",
        "Benefits",
        "Comparison",
        "Review",
        "Statistics",
        "Offers / Guarantee",
        "App Mockups",
    ],
}


def _parse_funnel_creatives(text: str) -> list[dict]:
    """Split a funnel-LLM response into creatives.

    Each creative is a block starting with ^ (the LLM is instructed to
    always start with ^). We return a list of {"prompt": <NanoBanana prompt>,
    "metadata": <full block including the metadata header>}.

    The "PROMPT:" line marks the start of the actual NanoBanana prompt; we
    extract everything after it as the prompt to send to the image model.
    """
    out: list[dict] = []
    for raw in text.split("^"):
        block = raw.strip()
        if not block:
            continue
        # Find PROMPT: marker (case-sensitive per spec, but be lenient with leading whitespace).
        marker_idx = -1
        for needle in ("\nPROMPT: ", "\nPROMPT:", "PROMPT: ", "PROMPT:"):
            idx = block.find(needle)
            if idx != -1:
                marker_idx = idx + len(needle)
                break
        if marker_idx == -1:
            # No PROMPT: marker — treat the whole block as the prompt (degraded fallback).
            out.append({"prompt": block, "metadata": block})
            continue
        prompt = block[marker_idx:].strip()
        if not prompt:
            continue
        out.append({"prompt": prompt, "metadata": block})
    return out


def generate_funnel_creatives(
    provider: "Provider",
    brand_dna: str,
    funnel_stage: str,
    form_fields: dict,
    product_image_url: str,
) -> list[dict]:
    """Ask the LLM for N funnel-stage creatives.

    form_fields keys (all values stringified before insertion):
      segment_breakdown — list of {"name": str, "count": int} (one entry per
        checked segment). Total = sum(count). At least one entry is required.
      marketing_angle, aspect_ratio, platform,
      target_persona, specifications, claims_refs, language,
      promotional_offer (BOF only), guarantee (BOF only)

    Returns a list of {"prompt", "metadata"} dicts, one per creative parsed
    from the LLM response.
    """
    stage = (funnel_stage or "").upper().strip()
    if stage not in FUNNEL_SYSTEM_PROMPTS:
        raise ValueError(f"Unknown funnel stage: {funnel_stage!r}")

    system_prompt = FUNNEL_SYSTEM_PROMPTS[stage]
    breakdown = form_fields.get("segment_breakdown") or []
    breakdown = [
        {"name": str(b.get("name", "")).strip(), "count": max(0, int(b.get("count", 0) or 0))}
        for b in breakdown if b.get("name")
    ]
    breakdown = [b for b in breakdown if b["count"] > 0]
    n = sum(b["count"] for b in breakdown)
    if n <= 0:
        raise ValueError("segment_breakdown must contain at least one segment with count > 0")

    breakdown_str = ", ".join(f"{b['count']} from \"{b['name']}\"" for b in breakdown)

    def _line(label: str, value) -> str:
        v = "" if value is None else str(value).strip()
        return f"{label}: {v if v else '(none — use your creative judgment based on Brand DNA)'}"

    user_lines = [
        f"SEGMENT BREAKDOWN: {breakdown_str}",
        f"NUMBER OF CREATIVES: {n}",
        _line("MARKETING ANGLE", form_fields.get("marketing_angle")),
        _line("ASPECT RATIO", form_fields.get("aspect_ratio") or "4:5"),
        _line("PLATFORM", form_fields.get("platform") or "Meta"),
        _line("TARGET PERSONA", form_fields.get("target_persona")),
        _line("SPECIFICATIONS", form_fields.get("specifications")),
        _line("Claims/headlines references", form_fields.get("claims_refs")),
        _line("LANGUAGE", form_fields.get("language") or "English"),
    ]
    if stage == "BOF":
        user_lines.append(_line("PROMOTIONAL OFFER", form_fields.get("promotional_offer")))
        user_lines.append(_line("GUARANTEE", form_fields.get("guarantee")))

    full_system_prompt = (
        f"{system_prompt}\n\n"
        "═══════════════════════════════════════\n"
        "BRAND DNA\n"
        "═══════════════════════════════════════\n\n"
        f"{(brand_dna or '').strip()}"
    )

    user_prompt = (
        "\n".join(user_lines)
        + f"\n\nGenerate exactly {n} {stage} creatives following all rules. "
        f"Distribute them across the SEGMENT BREAKDOWN above ({breakdown_str}) — "
        "respect the count per segment exactly. For each segment with count > 1, "
        "vary the concepts within that segment (never repeat the same concept twice). "
        "Treat 'Mix' as 'pick freely across allowed segments for this stage'. "
        "Each creative starts with ^ on its own line; no text before the first ^."
    )

    provider._log(
        "INFO",
        f"Requesting {n} {stage} creatives ({form_fields.get('language', 'English')})",
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url=product_image_url,
        system_prompt=full_system_prompt,
        label=f"LLM-funnel-{stage.lower()}",
    )
    creatives = _parse_funnel_creatives(text)
    if len(creatives) < n:
        provider._log("WARN", f"Only parsed {len(creatives)}/{n} creatives from LLM output")
    if len(creatives) > n:
        creatives = creatives[:n]
    if not creatives:
        raise RuntimeError(f"Could not parse any funnel creatives from LLM output:\n{text}")
    provider._log("OK", f"Parsed {len(creatives)} {stage} creatives")
    return creatives


TWIN_SYSTEM_PROMPT = """You are an expert image analyst and prompt engineer for text-to-image generation.

The user provides ONE reference image. Your job is to look at it carefully and produce a single text-to-image prompt that, run through NanoBanana 2 / NanoBanana Pro / GPT Image 2 in pure text-to-image mode (no reference attached), would create an image with the same essence — same medium, same style, same composition, same mood — but built from scratch by the model.

═══════════════════════════════════════
WHAT TO ANALYZE (silent step, never output)
═══════════════════════════════════════

For every image, identify:
- MEDIUM — photograph (studio / natural / phone) / 3D render (Pixar / hyperreal / abstract) / illustration (vector / watercolor / oil / pencil / digital painting) / collage / mixed
- SUBJECT — what is depicted (object, person, scene, organ, abstract shape). Describe generically — never name real people, brands or products
- COMPOSITION — focal point, framing (close-up / medium / wide), camera angle (eye-level / low / high / overhead), rule of thirds vs centered, asymmetry vs balance
- LIGHTING — direction, quality (hard / soft / diffused), color temperature, key/fill ratio, shadows behavior, any blown highlights
- COLOR PALETTE — 2-5 dominant colors with named families (warm beige, deep navy, muted lavender) plus the saturation and contrast level
- TEXTURES & MATERIALS — fabric, skin, metal, plastic, glass, wood, paper, the visible micro-detail
- MOOD / ATMOSPHERE — calm, dramatic, energetic, melancholic, clinical, dreamy, raw, polished
- TECHNIQUE CUES — focal length / DOF / grain / brush stroke / line weight / rendering style / post-processing

**MENTAL FILTER — strip all overlays before analyzing:** before you describe anything, mentally remove every text overlay, headline, caption, watermark, logo, wordmark, price tag, badge, sticker, UI element, and any added graphic that sits ON TOP of the underlying scene. Imagine the image as it would have been captured if no graphic designer had ever touched it. Your analysis describes ONLY this raw underlying visual. The composition you describe must be coherent without any text or overlay — the resulting prompt should produce a clean, text-free image even if the reference was a heavily-text-loaded ad.

═══════════════════════════════════════
HOW TO WRITE THE PROMPT
═══════════════════════════════════════

Single flowing paragraph in English. No line breaks. No markdown. No commentary. No labels like "PROMPT:".

Structure (loose, not enforced):
1. Lead with medium and style ("Photorealistic studio photograph of...", "3D Pixar-style render of...", "Hand-drawn watercolor illustration of...")
2. Describe the subject precisely but generically
3. Describe the composition and camera
4. Describe the lighting
5. Describe the color palette
6. Describe textures and materials
7. State the mood
8. End with technical cues that nail the look (e.g. "shot on a 50mm lens, shallow depth of field, natural window light, fine grain", or "ray-traced subsurface scattering, hyper-detailed materials, 8k", or "loose ink contour lines, soft watercolor wash, cold-pressed paper texture")

Length: 80 to 200 words. Never shorter, never longer.

═══════════════════════════════════════
USER HINT (optional)
═══════════════════════════════════════

If the user provides a HINT in the user message, treat it as a directive to MODIFY the recreation. Example hints:
- "use a blue/orange palette instead" → swap the palette
- "make the subject male" → adjust the subject
- "wider shot showing more environment" → change framing
- "shift to night scene" → recolor + relight

Apply the hint while keeping the rest of the analysis intact.

═══════════════════════════════════════
HARD RULES — NON NEGOTIABLE
═══════════════════════════════════════

1. NEVER name real public figures, real brands, or real products. Use generic descriptors ("a young woman with auburn hair in her late twenties").
2. **TEXT OVERLAYS ARE INVISIBLE** — completely ignore any text, headlines, captions, subtitles, watermarks, logos, wordmarks, price tags, badges, stickers, signs, UI screenshots, or written letterforms in the reference. Do NOT mention them, do NOT describe their position, do NOT preserve their layout, do NOT leave space for them. Pretend they do not exist. Describe only the underlying visual scene as if the image had been shot with no overlay applied.
   - Exception: if the entire image IS pure typography (e.g., an artistic typographic poster where text is the subject itself), describe the typographic style abstractly without quoting the actual words ("a bold serif headline filling 60% of the frame in deep ivory on charcoal background"), but never reproduce the exact wording.
3. NEVER mention copyrighted characters or IP.
4. NEVER include the words "PROMPT:", "Image:" or any header — output is the prompt only.
5. The output is exactly ONE flowing paragraph in English, 80-200 words. No bullet lists, no line breaks.
6. Do NOT mention the source image, do NOT say "the image shows" or "in the reference" — the prompt must read as if written from imagination, not from describing an existing image.

═══════════════════════════════════════
OUTPUT
═══════════════════════════════════════

Output the prompt and nothing else. No preamble, no postamble, no formatting."""


def analyze_image_for_twin(
    provider: "Provider",
    image_url: str,
    hint: str = "",
) -> str:
    """Vision-LLM call: analyze the reference image and return ONE text-to-image
    prompt. The prompt should be self-sufficient — running it through pure
    text-to-image will recreate the essence of the source.
    """
    h = (hint or "").strip()
    user_lines = [
        "Analyze the attached reference image and write the text-to-image prompt.",
        "",
        "IMPORTANT: ignore every text overlay, headline, caption, watermark, logo, "
        "price tag, badge, sticker, and UI element in the reference. Describe ONLY "
        "the underlying visual scene as if no graphic had ever been added on top — "
        "the resulting image must be clean and text-free.",
    ]
    if h:
        user_lines.append("")
        user_lines.append(f"HINT: {h}")
    text = provider.call_llm(
        prompt="\n".join(user_lines),
        image_url=image_url,
        system_prompt=TWIN_SYSTEM_PROMPT,
        label="LLM-twin",
    )
    cleaned = (text or "").strip()
    # Strip any leading "PROMPT:" label the LLM may have added despite rules.
    for prefix in ("PROMPT:", "Prompt:", "prompt:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if not cleaned:
        raise RuntimeError("Twin analysis returned empty text.")
    return cleaned


# ─── TWIN VIDEO (UGC hook recreation with brand product injection) ──────────
#
# Different intent than TWIN_SYSTEM_PROMPT: instead of recreating an image, we
# clone a UGC scene from a frame of the user's old video and inject their NEW
# brand product into it. Output is structured (JSON-ish) with two fields so
# the pipeline can route them: `scene` drives the start-frame image generation,
# `action` drives the Kling video animation.

TWIN_VIDEO_SYSTEM_PROMPT = """You are a creative director writing a single still-image prompt for NanoBanana 2. The user gives you ONE frame from a real UGC ad (image 1) and a NEW product (image 2). Your job: describe ONE photorealistic still that recreates the SAME UGC vibe — same kind of person, same outfit, same room, same lighting, same camera vibe — but with the new product naturally held in the same way, integrated as if it had really been photographed there.

Critical mindset: this is NOT a copy-paste edit. It IS a regeneration that strongly mirrors image 1 while putting `@product` (image 2) into the person's hand with REAL light and shadow on it — not a pasted layer. NanoBanana will see both images and compose; your prompt has to give it permission to relight the product so it belongs in the scene.

═══════════════════════════════════════
WHAT TO LOOK FOR IN THE SOURCE FRAME
═══════════════════════════════════════

Silently catalog (then describe in the prompt):
- Subject: gender, approximate age, ethnicity descriptor, hair, facial hair, build, accessories — describe generically, never name a real person
- Wardrobe: top, fabric, drape, any visible jewellery
- Setting: room type, walls, decor cues (lamp shape, shelf, ceiling light, doorway)
- Lighting: warm/cool, direction, hardness, time-of-day feel — this MUST be applied to the product so it looks like it was lit by the same lamp
- Camera: phone selfie / front camera / mirror selfie, distance, angle, slight asymmetry
- Hand & grip: which hand, at what height, fingers wrapping, thumb position — the product sits in the same grip
- Aesthetic: raw iPhone capture / film grain / portrait blur — describe the rendering style explicitly

Mentally STRIP every overlay (caption, watermark, brand logo on the original product) — describe ONLY the underlying scene.

═══════════════════════════════════════
HOW TO WRITE THE PROMPT
═══════════════════════════════════════

Single flowing paragraph in English, 120-220 words. No line breaks. No labels. Treat the source frame as the dominant visual reference (mention "matching the lighting, color temperature, and mood of the reference frame") and the product as a hard constraint (mention "@product", describe its packaging from the user's PRODUCT block, instruct that it must be relit by the room's light source so it doesn't look pasted, with realistic shadows where the hand grips it and a natural reflection where the lamp would hit it).

Suggested structure:
1. Lead with the medium and aesthetic ("Raw iPhone front-camera selfie" or "Mirror selfie photo on iPhone, no LUT, no portrait mode")
2. Describe the subject precisely but generically
3. Describe the wardrobe and any micro-details
4. Describe the setting in 2-3 sensory cues
5. Describe the lighting as it falls on the face AND on @product
6. Describe the hand pose around @product
7. End with technical cues that nail the look ("shot on iPhone front camera, 28mm equivalent, slight chromatic aberration, gentle film grain in the shadows")

═══════════════════════════════════════
WHAT THE USER'S PRODUCT IS
═══════════════════════════════════════

The user message contains a PRODUCT block describing the new product (packaging shape, container, label colors, format, signature cues). Use those details so NanoBanana renders the right packaging even before image 2 reinforces it. Refer to the product as `@product` in the prompt.

═══════════════════════════════════════
OUTPUT FORMAT — STRICT
═══════════════════════════════════════

Output exactly two labeled blocks, in this order, nothing else:

SCENE:
<the single 120-220 word paragraph described above. The fresh still that NanoBanana renders. Reference image 1 explicitly as "matching the lighting and mood of the reference frame" and refer to the product as `@product`. Demand that the product be RELIT by the scene's light so it integrates rather than looking pasted.>

ACTION:
<one flowing paragraph, 50-120 words, describing the 5-10s motion for Kling 3.0 starting from the rendered frame. Lead with `^`. Describe a NATURAL UGC moment: subtle blink, small genuine half-smile, the person bringing the product slightly closer to the camera as if about to speak about it, mouth opening slightly to start a sentence. NO scripted lines, NO words spoken on screen — Kling can't lipsync anyway. Keep the product orientation absolutely fixed (no rotation, no flip), label staying readable. End with the token `@product` so Kling locks the product reference.>

═══════════════════════════════════════
COLORIMETRY — MUST MATCH SOURCE EXACTLY
═══════════════════════════════════════

Always close the SCENE paragraph with a sentence that locks the look to the source frame's chromatic identity, e.g.:
"Color grade and white balance match the reference frame exactly: identical color temperature (warm tungsten / cool daylight / mixed — pick whichever matches), identical tonal curve, identical saturation level, no shift toward warmer or cooler tones, the rendered still must read as captured by the same phone in the same room at the same time of day as the reference."

Be EXPLICIT about Kelvin temperature direction (warm / neutral / cool) and dominant color cast (e.g. amber, beige, magenta) so NanoBanana doesn't drift toward its default neutral white balance.

═══════════════════════════════════════
HARD RULES
═══════════════════════════════════════

1. NEVER write "edit", "replace", "swap", "preserve", "pixel-perfect", "do not regenerate" — those collapse NanoBanana into a pasted-layer composite. We want a fresh photoreal render strongly informed by image 1.
2. ALWAYS instruct that `@product` is relit by the scene so it does not look like a sticker.
3. ALWAYS lock the white balance and color grade to the reference frame in the closing sentence.
4. Generic descriptors only — never name real people or copyrighted IP.
5. No captions, no on-screen text, no spoken words.
6. Output ONLY the two labeled blocks. No preamble, no postamble, no markdown."""


def analyze_for_twin_video(
    provider: "Provider",
    frame_url: str,
    product_description: str,
    hint: str = "",
) -> dict:
    """Vision-LLM call: read a UGC ad frame and return {scene, action} prompts
    tailored to clone the scene with a different product injected.

    `product_description` is a short paragraph from the brand's DNA describing
    the packaging (label colors, format, container shape, signature cues). It
    is interpolated into the SCENE block so NanoBanana renders the new product
    accurately even before the image-to-image reference is applied.

    Returns: {"scene": <str>, "action": <str>}.
    """
    user_lines = [
        "Reference UGC frame: [attached as image 1]",
        "",
        "PRODUCT (the user's new product, supplied as image 2 to NanoBanana):",
        product_description.strip() or "(no product description supplied)",
    ]
    h = (hint or "").strip()
    if h:
        user_lines.append("")
        user_lines.append(f"HINT: {h}")
    user_lines.append("")
    user_lines.append(
        "Output the two labeled blocks SCENE: and ACTION: per the system rules."
    )
    text = provider.call_llm(
        prompt="\n".join(user_lines),
        image_url=frame_url,
        system_prompt=TWIN_VIDEO_SYSTEM_PROMPT,
        label="LLM-twin-video",
    )
    raw = (text or "").strip()
    # Forgiving parser. Accept both EDIT: (new edit-mode) and SCENE: (legacy
    # rewrite-mode) as the first label so older runs don't blow up if the LLM
    # falls back to the previous wording. Stored under key "scene" to keep
    # downstream consumers (page UI, render_frame call site) untouched.
    import re
    m_edit = re.search(
        r"(?:EDIT|SCENE)\s*:\s*(.*?)(?=\n\s*ACTION\s*:|$)",
        raw, re.IGNORECASE | re.DOTALL,
    )
    m_action = re.search(r"ACTION\s*:\s*(.*)$", raw, re.IGNORECASE | re.DOTALL)
    scene = (m_edit.group(1) if m_edit else raw).strip()
    action = (m_action.group(1) if m_action else "").strip()
    if not action:
        # Last-ditch: prefix the edit instruction with ^ so Kling still gets
        # a usable action prompt even on degraded LLM output.
        action = "^ " + scene
    if not action.lstrip().startswith("^"):
        action = "^ " + action
    if "@product" not in action:
        action = action.rstrip() + " @product"
    if not scene:
        raise RuntimeError("Twin video analysis returned empty EDIT block.")
    return {"scene": scene, "action": action}


def soften_prompt(provider: "Provider", prompt: str, ad_url: str) -> str:
    """Ask the LLM to rewrite a content-filter-rejected prompt."""
    text = provider.call_llm(
        prompt="Rewrite this NanoBanana prompt to pass content filters:\n\n" + prompt,
        image_url=ad_url,
        system_prompt=SOFTENER_SYSTEM_PROMPT,
        label="LLM-soften",
    ).strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


# ─── STATIC AD ITERATION REGISTRY ───────────────────────────────────────────
#
# Each axis is a self-describing entry: an LLM "what to detect + how to vary"
# system prompt and an image-edit prompt template applied per variant. The
# core dispatcher (run_iterate) calls analyze_for_axis() to produce N variant
# strings, then loops through call_image() with the per-variant edit prompt.
#
# Adding a new axis = add an entry here. No code change anywhere else.

_AXIS_PROMPT_HEADER = """You are an expert ad iterator analyzing one static ad image. Output STRICT JSON only — no preamble, no markdown, no commentary."""

CONCEPT_CATALOG = [
    {"slug": "bullet_points", "label": "Bullet points", "prompt_label": "Bullet points", "hint": "vertical or horizontal list of 3-5 short bullets with icons or arrows, headline on top, CTA at the bottom. All bullet copy MUST be written in the target language specified at the end of this prompt."},
    {"slug": "problem_solution", "label": "Problème / Solution", "prompt_label": "Problem / Solution", "hint": "two-zone layout — top half shows the problem clearly, bottom half shows the solution with the product. Any zone labels rendered on the image must be in the target language."},
    {"slug": "before_after", "label": "Avant / Après", "prompt_label": "Before / After", "hint": "split in two halves — left = problem state, right = result state, with clear labels (labels rendered in the TARGET LANGUAGE specified at the end of this prompt — NEVER hardcode 'avant'/'après'/'before'/'after' in any specific language unless that matches the target). WHEN the product's promise is a human transformation (focus, energy, calm, sleep, mood, skin, hair, body, posture, confidence): the SAME person must appear on BOTH sides, in the SAME framing and SAME angle, but in VISIBLY DIFFERENT states — left side embodies the problem (slumped posture, tired eyes, head-in-hands, scattered, frowning, low energy in their face and body), right side embodies the result (upright posture, sharp eyes, smile, in-flow energy, visibly energized). The state difference must be readable in under 1 second from the human alone — not from the props. Product visible in both halves but secondary (max 20% of each half), human is the hero. ONLY when the product's promise is NOT a human transformation (cleaning product, kitchen tool, plant fertilizer, etc.) is it acceptable to show two object/environment states without a person. STRICTLY FORBIDDEN: a before/after that only swaps background color or props around the same product packshot — that fails the brief."},
    {"slug": "split_benefit", "label": "Split + bénéfice", "prompt_label": "Split + benefit", "hint": "split layout — left side product hero, right side big-headline benefit highlight (headline copy in the target language)"},
    {"slug": "split_offer", "label": "Split + offre", "prompt_label": "Split + offer", "hint": "split layout — left side product hero, right side offer block with deal and CTA (all copy in the target language)"},
    {"slug": "us_vs_them", "label": "Us VS Them", "prompt_label": "Us vs Them", "hint": "comparative two-column layout — left column 'them' (competitor flaws in red), right column 'us' (advantages in green). Column headers and copy in the TARGET LANGUAGE."},
    {"slug": "us_vs_them_them", "label": "Us VS Them VS Them", "prompt_label": "Us vs Them vs Them", "hint": "three-column comparative — us (winner) vs two competitors, our column highlighted. All copy in the target language."},
    {"slug": "social_proof", "label": "Social proof", "prompt_label": "Social proof", "hint": "centered review card with 5 stars, customer name, short review text + product packshot (all copy in the target language)"},
    {"slug": "offer_forward", "label": "Offre en avant", "prompt_label": "Offer forward", "hint": "offer-led — biggest element is the price/deal/percentage, product secondary (currency + copy in the target language)"},
    {"slug": "hand_writing", "label": "Hand writing", "prompt_label": "Hand writing", "hint": "designed as a handwritten note style on paper/post-it/notebook texture (handwritten copy in the target language)"},
    {"slug": "long_text", "label": "Textuel long", "prompt_label": "Long form text", "hint": "text-heavy editorial — long paragraph as the dominant element, product image small (paragraph in the target language)"},
    {"slug": "native_ugc", "label": "Native FB/IG/TT", "prompt_label": "Native social-media post", "hint": "designed as a native social-media post (Facebook/Instagram/TikTok screenshot style) — UI chrome and any visible copy in the target language"},
    {"slug": "headline_only", "label": "Headline only", "prompt_label": "Headline only", "hint": "minimal — giant typographic headline filling 60% of the frame, product small (headline in the target language)"},
    {"slug": "statistics", "label": "Statistiques", "prompt_label": "Statistics", "hint": "ONE hero statistic that occupies 40-60% of the frame (giant percentage or number, brand-color typography, immediately legible). AT MOST one secondary supporting stat, rendered much smaller (~15% of hero size), placed off-axis. Single source line in fine print. Product visible but clearly secondary (max 20% of frame). All accompanying copy (caption, source line, supporting stat label) in the target language. STRICTLY FORBIDDEN: more than 2 numerical data points total, donut + bar + people-icons stacked, multi-stat dashboard layouts, infographic walls. The whole ad must read as 'one killer number that stops the scroll' — not as a report."},
    {"slug": "product_only", "label": "Produit simple", "prompt_label": "Product only", "hint": "minimalist product packshot — product centered on solid backdrop, no text"},
]

AWARENESS_CATALOG = [
    {"slug": "unaware", "label": "Unaware", "hint": "audience doesn't know they have a problem — lead with curiosity hook, no product mention upfront, build awareness of the underlying issue"},
    {"slug": "problem_aware", "label": "Problem-aware", "hint": "audience knows the problem — agitate the pain, then introduce the solution"},
    {"slug": "solution_aware", "label": "Solution-aware", "hint": "audience knows solutions exist — differentiate yours from alternatives, lead with 'why ours' angle"},
    {"slug": "product_aware", "label": "Product-aware", "hint": "audience knows your product — drive desire with social proof, benefits, testimonials"},
    {"slug": "most_aware", "label": "Most-aware (BoFu)", "hint": "audience ready to buy — lead with offer, urgency, scarcity, guarantee"},
]

STYLE_CATALOG = [
    {"slug": "photoreal_ugc", "label": "Photoreal UGC", "hint": "raw iPhone UGC capture, no LUT, no grading, slight grain, candid framing"},
    {"slug": "studio_polished", "label": "Studio polished", "hint": "polished commercial studio photography, soft key light, glossy surfaces, magazine-grade"},
    {"slug": "editorial", "label": "Editorial", "hint": "editorial magazine spread, premium serif typography hierarchy, generous negative space"},
    {"slug": "flat_design", "label": "Flat design", "hint": "flat 2D design, no gradients, solid colors, geometric shapes, bold sans"},
    {"slug": "3d_pixar", "label": "3D Pixar", "hint": "Pixar-style 3D render, smooth subsurface scattering, painterly bokeh, warm cinematic grade"},
    {"slug": "claymation", "label": "Claymation", "hint": "stop-motion claymation, hand-sculpted clay surfaces with fingerprint marks, glossy plasticine"},
    {"slug": "illustrated", "label": "Illustrated", "hint": "hand-drawn illustration, watercolor or ink texture, organic shapes"},
    {"slug": "brutalist", "label": "Brutalist", "hint": "brutalist design, harsh typography, oversized text, raw geometric blocks, no decoration"},
    {"slug": "collage", "label": "Collage", "hint": "paper cutout collage, layered torn paper, hand-cut edges, textured cardstock"},
    {"slug": "minimalist", "label": "Minimalist", "hint": "minimalist clean design, tons of white space, single accent color, ultra-restrained"},
]

OFFER_CATALOG = [
    {"slug": "bundle_2", "label": "Bundle x2", "hint": "bundle of 2 with discount — show original price crossed out, bundle price highlighted"},
    {"slug": "bundle_3", "label": "Bundle x3", "hint": "bundle of 3 with bigger discount, biggest visual element is the savings"},
    {"slug": "bundle_premium", "label": "Premium bundle", "hint": "premium bundle (4+ units) with bonuses (free guide, freebies, free shipping) prominently shown"},
    {"slug": "bogo", "label": "1 + 1 free", "hint": "buy one get one free (BOGO) framing — 1+1 mechanic as the main hook"},
    {"slug": "percentage_off", "label": "% off", "hint": "percentage discount (-30%, -50%) huge and centered, original price secondary"},
    {"slug": "price_anchor", "label": "Price anchor", "hint": "price anchoring — original price visibly crossed out, new price highlighted in the brand accent"},
    {"slug": "free_shipping", "label": "Free shipping", "hint": "free-shipping mechanic as the main hook (text rendered in the TARGET LANGUAGE — e.g. 'Free shipping' / 'Livraison offerte' / 'Envío gratis' depending on language), secondary product visual"},
    {"slug": "money_back", "label": "Money-back", "hint": "money-back guarantee badge prominent (e.g. '90-day money-back' rendered in the TARGET LANGUAGE), reassurance-led"},
    {"slug": "limited_time", "label": "Limited time", "hint": "limited-time urgency (offer expires X) front and center, countdown vibe"},
    {"slug": "volume_discount", "label": "Volume discount", "hint": "volume tier mechanic — 1 unit = €X, 2 units = €Y/unit, 3+ units = €Z/unit shown as a table"},
    {"slug": "gift_with_purchase", "label": "Gift with purchase", "hint": "free gift with purchase mechanic (e.g. 'Free gift over $X' rendered in the TARGET LANGUAGE) shown as the main hook"},
    {"slug": "subscription_save", "label": "Subscription save", "hint": "subscription discount (save X% with auto-renew) framed as the smart option"},
]


# Native UGC selfie formats. Used by the `native_ugc_selfie` iteration axis,
# which regenerates a polished studio ad into a raw iPhone selfie keeping
# ONLY the source product packaging as the immutable hero element.
NATIVE_UGC_FORMATS = [
    {
        "slug": "mirror_selfie",
        "label": "Mirror selfie",
        "hint": (
            "person standing in front of a bathroom or full-length mirror, holding "
            "the product up at chest level, smartphone partially visible in the "
            "reflection covering part of the face, ambient overhead bathroom light "
            "or natural window light, real bathroom clutter visible in the reflection "
            "(towels, toiletries, mirror smudges)"
        ),
    },
    {
        "slug": "pov_arm_extended",
        "label": "POV arm extended",
        "hint": (
            "first-person POV with one arm extended toward the camera holding the "
            "product as the foreground hero, face partially visible behind the product "
            "(forehead and eyes peeking, or chin and smile), slight motion blur from "
            "handheld phone, casual home or street setting blurred behind"
        ),
    },
    {
        "slug": "in_use_moment",
        "label": "In-use moment",
        "hint": (
            "person captured mid-use of the product (drinking, applying, eating, "
            "mixing, opening) in an unposed candid moment, photographed from across "
            "the room or just above eye-level, real lived-in setting (kitchen "
            "counter / bedroom / desk / gym locker room), natural ambient light only"
        ),
    },
    {
        "slug": "unboxing_reaction",
        "label": "Unboxing reaction",
        "hint": (
            "person just received the product, holding it close to chest or beside "
            "the face, fresh packaging still visible (no wear), genuine first-look "
            "facial expression (surprised, delighted, intrigued, eyebrow-raise), "
            "couch or kitchen counter or entryway setting, daytime natural light"
        ),
    },
    {
        "slug": "morning_routine",
        "label": "Morning routine",
        "hint": (
            "person captured in their morning routine with the product integrated "
            "naturally (next to coffee mug on counter, on bathroom vanity beside "
            "toothbrush, on bedside table beside phone), soft morning window light, "
            "person partially in frame (hand reaching for product, or in pajamas in "
            "the background), no styling effort visible"
        ),
    },
    {
        "slug": "duo_friend_share",
        "label": "Duo / friend share",
        "hint": (
            "two friends in the frame, one holding the product up while talking to "
            "the other, both reacting genuinely (one curious, one already convinced), "
            "casual social setting (couch, café table, kitchen island), candid "
            "phone-snap framing, no posed energy"
        ),
    },
]


ITERATION_AXES: dict[str, dict] = {
    "headline": {
        "label": "Headline",
        "describe": "the main headline text",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the MAIN HEADLINE — the largest, most prominent text, typically at the top or center. Ignore CTAs, fine print, sub-headlines, badges, prices.

Classify its style: format ∈ {question, declarative, imperative, numerical, barred, contrast, exclamation, list}, tone ∈ {empathetic, urgent, shocking, playful, clinical, conversational, authoritative}, length ∈ {short, medium, long}.

Generate {N} alternative headlines in the SAME style category but with different angles, phrasings, or word choices. Variants must be clearly different from the original (not paraphrases). Match the source language. Never name real people or copyrighted IP.

OUTPUT:
{
  "detected": "the exact original headline text",
  "style_summary": "format/tone/length",
  "variants": ["headline 1", "headline 2", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) by replacing ONLY the main "
            "headline text with: \"{variant}\". Match the original "
            "headline's font, weight, size, color, alignment, and position "
            "exactly. Keep every other pixel of the source unchanged — "
            "product, person, layout, sub-headline, CTA, background, "
            "lighting, colors, typography style."
        ),
    },
    "actor": {
        "label": "Actor",
        "describe": "the person featured in the ad",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the main PERSON in the ad. Describe them generically — never name a real person. Capture: gender, approximate age, ethnicity descriptor, hair, build, vibe.

Generate {N} alternative personas that vary on age, gender, ethnicity, or lifestyle while keeping the ad context plausible. Each variant is one short sentence (~15 words) describing the new person.

OUTPUT:
{
  "detected": "short generic description of the current person",
  "style_summary": "demographic summary",
  "variants": ["new person description 1", "new person description 2", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) by replacing the person with: "
            "{variant}. Keep every other element pixel-for-pixel — the "
            "same product, packaging, props, room, decor, lighting, "
            "framing, camera angle, all overlays and text. The new person "
            "must occupy the same position, pose, and gesture as the "
            "original. Match the original lighting on the new person's "
            "skin and hair."
        ),
    },
    "decor": {
        "label": "Décor",
        "describe": "the setting / background of the ad",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the SETTING / décor of the ad: room type, decor cues, lighting direction, time of day, aesthetic.

Generate {N} alternative settings that change the location while keeping the brand/product plausibly placed there. Each variant is one short sentence (~15 words) describing the new setting (e.g. "scandinavian bathroom with marble counter, soft morning light").

OUTPUT:
{
  "detected": "short description of the current setting",
  "style_summary": "lighting + aesthetic summary",
  "variants": ["new setting 1", "new setting 2", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) by replacing the setting / "
            "background with: {variant}. Keep every other element pixel-"
            "for-pixel — the same person, pose, product, packaging, all "
            "overlays and text, the framing and camera angle. The new "
            "setting must light the subject realistically (matching the "
            "described lighting direction and color temperature)."
        ),
    },
    "concept": {
        "label": "Concept",
        "describe": "the structural concept of the ad",
        "catalog": CONCEPT_CATALOG,
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current CONCEPT (visual structure) from this list:
bullet_points, problem_solution, before_after, split_benefit, split_offer, us_vs_them, social_proof, offer_forward, hand_writing, long_text, native_ugc, headline_only, statistics, product_only.

Generate {N} alternative concepts from the SAME list — different concepts each time — that would work for this brand and product. Each variant is the concept slug + one short sentence explaining how it would re-structure the visual.

OUTPUT:
{
  "detected": "current_concept_slug",
  "style_summary": "what defines the current concept visually",
  "variants": ["concept_slug — how it would be restructured", "..."]
}""",
        "edit_prompt": (
            "Take the source image (image 1) as the brand/product/copy "
            "reference and re-design it following this NEW concept: "
            "{variant}. You may regenerate the entire layout to fit the "
            "new concept, but preserve: the exact same product packaging "
            "(logo, label text, color, shape), the same brand identity "
            "(colors, typography family, voice), and the core message of "
            "the original ad. The new concept's visual structure replaces "
            "the original."
        ),
    },
    "awareness": {
        "label": "Awareness",
        "describe": "the funnel-stage / awareness level targeted",
        "catalog": AWARENESS_CATALOG,
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current AWARENESS level of the targeted audience based on the copy + visuals:
unaware, problem_aware, solution_aware, product_aware, most_aware.

Generate {N} alternative awareness levels (each different from the original) and for each, rewrite the messaging to fit. Each variant is the awareness slug + the rewritten headline + a one-line sub-headline.

OUTPUT:
{
  "detected": "current_awareness_slug",
  "style_summary": "why the current copy targets this awareness level",
  "variants": ["awareness_slug | new headline | new sub-headline", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) for a DIFFERENT awareness "
            "level. Update the headline, sub-headline, and CTA wording to "
            "match: {variant}. Keep every visual element pixel-for-pixel "
            "— same product, person, room, decor, layout, color palette, "
            "typography style. Only the text content changes."
        ),
    },
    "offer": {
        "label": "Offre",
        "describe": "the deal / pricing / bundle shown",
        "catalog": OFFER_CATALOG,
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current OFFER block in the ad (if any) — bundle, discount %, price point, free shipping, money-back, BOGO, volume deal, etc.

Generate {N} alternative offer mechanisms in the same language and tone. Each variant is one short sentence (~12 words) describing the new offer pitch and any numbers.

OUTPUT:
{
  "detected": "the current offer mechanism + any numbers, or 'no offer detected'",
  "style_summary": "the offer style (discount/bundle/volume/guarantee/...)",
  "variants": ["new offer 1", "new offer 2", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) by replacing the offer block "
            "with: {variant}. Keep every other element pixel-for-pixel — "
            "person, product, background, headline, CTA, layout, design "
            "system. Match the original offer block's position, scale, "
            "typography family, and color treatment."
        ),
    },
    "style": {
        "label": "Style",
        "describe": "the overall visual aesthetic",
        "catalog": STYLE_CATALOG,
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current visual STYLE / aesthetic of the ad: photoreal UGC, polished studio, illustrated, 3D render, flat design, brutalist, editorial magazine, hand-drawn, claymation, etc.

Generate {N} alternative styles (clearly different from the current one). Each variant is one short label + a one-line rendering description (e.g. "claymation — hand-sculpted clay figure with visible fingerprints, glossy plasticine skin").

OUTPUT:
{
  "detected": "current style label",
  "style_summary": "key rendering cues",
  "variants": ["new style label — rendering description", "..."]
}""",
        "edit_prompt": (
            "Re-render the source image (image 1) in this NEW aesthetic: "
            "{variant}. Keep the same subject, product, composition, and "
            "all text overlays. Apply the new rendering technique uniformly "
            "to every visual element."
        ),
    },
    "palette": {
        "label": "Palette",
        "describe": "the color palette",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current color PALETTE of the ad — 2-5 dominant colors with named families (warm beige, deep navy, muted lavender) plus saturation and contrast level.

Generate {N} alternative palettes appropriate for the brand category. Each variant is one short label + the 2-5 dominant hex codes or named colors.

OUTPUT:
{
  "detected": "current palette description",
  "style_summary": "saturation + contrast",
  "variants": ["palette label — color1, color2, color3, ...", "..."]
}""",
        "edit_prompt": (
            "Re-render the source image (image 1) with this NEW color "
            "palette: {variant}. Recolor backgrounds, surfaces, text "
            "blocks, accent strokes accordingly. Keep the product's actual "
            "packaging colors UNCHANGED — the product must remain "
            "recognizable. Keep composition, person, layout, text content "
            "all pixel-for-pixel except for the color recoloring."
        ),
    },
    "cta": {
        "label": "CTA",
        "describe": "the call-to-action button or text",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current CTA — the call-to-action button or text (e.g. "Découvrir", "Shop now", "Try it free", "+50% today").

Generate {N} alternative CTA wordings in the same language. Each variant is short (1-5 words), action-oriented, and conversion-focused.

OUTPUT:
{
  "detected": "the current CTA text",
  "style_summary": "tone + length",
  "variants": ["CTA 1", "CTA 2", "..."]
}""",
        "edit_prompt": (
            "Edit the source image (image 1) by replacing ONLY the CTA "
            "button/text with: \"{variant}\". Match the original CTA's "
            "font, color, background, border-radius, position, and size. "
            "Keep every other element pixel-for-pixel."
        ),
    },
    "layout": {
        "label": "Layout",
        "describe": "the composition / layout of the elements",
        "analyzer": _AXIS_PROMPT_HEADER + """

Identify the current LAYOUT: where the headline, sub-headline, product, person, CTA, and offer are positioned (top/middle/bottom, left/center/right), and the overall hierarchy.

Generate {N} alternative layouts with a different composition. Each variant is one paragraph (~25 words) describing the new arrangement (e.g. "product centered occupying 60% of frame, headline reduced to bottom-left in 2 lines, CTA sticky at bottom-right corner").

OUTPUT:
{
  "detected": "short description of the current layout",
  "style_summary": "hierarchy summary",
  "variants": ["new layout description 1", "..."]
}""",
        "edit_prompt": (
            "Re-design the source image (image 1) with this NEW layout: "
            "{variant}. Keep the same product, brand identity, color "
            "palette, typography family, and the SAME message content. "
            "Only the composition / positioning of elements changes."
        ),
    },
    "native_ugc_selfie": {
        "label": "Native UGC",
        "describe": "regenerated as a raw iPhone selfie keeping ONLY the product",
        "catalog": NATIVE_UGC_FORMATS,
        "analyzer": _AXIS_PROMPT_HEADER + """

Extract the PRODUCT from the source ad — packaging shape, color palette, label/logo text, category. Ignore decor, current actor, copy overlays, design layout.

Generate {N} native UGC selfie scenarios, one per requested format. Each variant must be one short paragraph (~30 words) combining: the requested format, a believable real setting, the lighting source, the actor's demographic that plausibly matches the product's ICP (if a brand persona context is provided in the system prompt, use it; else infer from product category), and a brief expression cue.

OUTPUT:
{
  "detected": "product packaging description + product category",
  "style_summary": "inferred ICP demographic",
  "variants": ["<format slug> — <setting>, <actor>, <lighting>, <expression>", "..."]
}""",
        "edit_prompt": (
            "Regenerate the image as a raw iPhone UGC selfie photo.\n\n"
            "PRESERVE FROM IMAGE 1 (immutable): ONLY the exact product "
            "packaging — same logo, same label text, same colors, same shape, "
            "same proportions, same readable copy on the pack. The product is "
            "the only element carried over from the source.\n\n"
            "REPLACE EVERYTHING ELSE entirely according to this scenario: "
            "{variant}\n\n"
            "AESTHETIC RULES (must follow strictly):\n"
            "- Raw iPhone selfie aesthetic: handheld angle, slight optical "
            "micro-flaws, real visible skin texture (pores, slight redness, "
            "no airbrushing), slight motion blur acceptable.\n"
            "- Natural ambient light only — overhead bathroom light, soft "
            "window light, fluorescent kitchen — NEVER studio softbox, NEVER "
            "rim lights, NEVER lens flares, NEVER professional product lighting.\n"
            "- Real lived-in setting — visible household clutter, normal "
            "surfaces, real-world background depth.\n"
            "- ABSOLUTELY NO text overlays, NO graphic callouts, NO design "
            "elements, NO arrows, NO badges, NO typography work, NO logos "
            "other than what is printed on the product packaging itself.\n"
            "- The output must read as a real customer's iPhone Story post, "
            "NOT a brand campaign or studio shot. If it looks polished, you "
            "have failed the brief."
        ),
    },
}


def _iter_actor_prompt_with_description(description: str, n_variants: int) -> str:
    """When the user supplies a free-text actor description, swap the default
    persona-from-image analyzer for one that produces N micro-variations of
    that exact description (same person, same vibe — only context/expression/
    angle micro-shifts so the N edits don't collapse into duplicates)."""
    return _AXIS_PROMPT_HEADER + f"""

The user has explicitly described the actor they want for this ad:

USER-PROVIDED ACTOR DESCRIPTION:
{description}

Generate {n_variants} variants of the SAME PERSON (matching every demographic and styling cue above), differing only on micro-context cues (expression, micro-pose, gaze direction, energy) so the rendered images don't all collapse into the same shot. NEVER change gender, age, ethnicity, build, or styling from what the user described.

OUTPUT:
{{
  "detected": "user-provided",
  "style_summary": "{description[:90]}",
  "variants": ["variant description 1", "variant description 2", "..."]
}}"""


def _inject_iter_context(
    sys_prompt: str,
    *,
    brand_name: str | None = None,
    brand_dna: str | None = None,
    language: str | None = None,
) -> str:
    """Prepend brand/language framing to an iteration analyzer system prompt
    when they are provided. No-op when both are empty (preserves existing
    behavior for callers that don't pass these)."""
    blocks: list[str] = []
    if brand_dna and brand_dna.strip():
        nm = (brand_name or "the brand").strip()
        blocks.append(
            f"=== BRAND CONTEXT ===\n"
            f"Brand: {nm}\n"
            f"DNA: {brand_dna.strip()}\n"
            f"=== END BRAND CONTEXT ===\n\n"
            f"Use this brand's voice, tone, and ICP for any generated copy or persona. "
            f"Persona variants must plausibly match this brand's target audience.\n"
        )
    if language and language.strip():
        blocks.append(
            f"=== TARGET LANGUAGE ===\n"
            f"All text content in variants (headlines, CTAs, sub-headlines, offer copy, "
            f"awareness messaging) MUST be written in {language.strip()}. Use idiomatic, "
            f"native-level {language.strip()} — never literal translation.\n"
            f"=== END TARGET LANGUAGE ===\n"
        )
    if not blocks:
        return sys_prompt
    return "\n".join(blocks) + "\n" + sys_prompt


def analyze_for_axis(
    provider: "Provider",
    image_url: str,
    axis_key: str,
    n_variants: int,
    *,
    language: str | None = None,
    brand_name: str | None = None,
    brand_dna: str | None = None,
    actor_description: str | None = None,
) -> dict:
    """Generic axis analyzer. Routes to ITERATION_AXES[axis_key], calls the
    LLM with the axis-specific system prompt + an N-templated user prompt,
    and parses the strict JSON output.

    Optional context:
      - language: forces all text variants into the named language.
      - brand_name / brand_dna: injects brand voice + ICP framing.
      - actor_description: only honored for axis='actor'. Replaces the
        from-image persona analyzer with one that micro-varies the user's
        described persona instead.

    Returns {detected, style_summary, variants}. Raises RuntimeError on
    empty / unparseable output.
    """
    axis = ITERATION_AXES.get(axis_key)
    if not axis:
        raise RuntimeError(f"Unknown iteration axis: {axis_key!r}")
    if axis_key == "actor" and actor_description and actor_description.strip():
        base_sys = _iter_actor_prompt_with_description(
            actor_description.strip(), n_variants
        )
    else:
        base_sys = axis["analyzer"].replace("{N}", str(n_variants))
    sys_prompt = _inject_iter_context(
        base_sys,
        brand_name=brand_name,
        brand_dna=brand_dna,
        language=language,
    )
    user_prompt = (
        f"Analyze the attached static ad and produce {n_variants} variants "
        f"on the {axis['describe']} axis. Output the strict JSON per the "
        f"system rules — nothing else."
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url=image_url,
        system_prompt=sys_prompt,
        label=f"LLM-iter-{axis_key}",
    )
    raw = (text or "").strip()
    if raw.startswith("```"):
        import re
        m = re.search(r"^```(?:json)?\s*\n(.*?)\n```\s*$", raw, re.DOTALL)
        if m:
            raw = m.group(1)
    import json as _json
    try:
        out = _json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"{axis_key} iterator returned unparseable JSON: {e}\n\n{raw[:400]}")
    variants = out.get("variants") or []
    if not isinstance(variants, list) or not variants:
        raise RuntimeError(f"{axis_key} iterator returned no variants: {raw[:400]}")
    out["variants"] = variants[:n_variants]
    return out


# Backward-compat alias for the previous single-axis core function call site.
def analyze_and_iterate_headline(
    provider: "Provider",
    image_url: str,
    n_variants: int,
) -> dict:
    out = analyze_for_axis(provider, image_url, "headline", n_variants)
    # Map the new generic keys onto the previous shape so existing callers
    # keep working without touching their parsing.
    return {
        "detected_headline": out.get("detected", ""),
        "style": {"summary": out.get("style_summary", "")},
        "variants": out.get("variants", []),
    }


# ─── SWAP PRODUCT (Seedance v2 video-to-video) ──────────────────────────────
#
# The Swap Product page takes a competitor's video + the user's product image,
# detects what's being held in the source, and writes a single-paragraph swap
# brief for `seedance-v2.0-video-edit`. The brief MUST reference the user's
# packshot via `@image1` — that's the placeholder Seedance resolves to the
# images_list[0] at request time. Without `@image1` the model will regenerate
# the source product instead of swapping it.

SWAP_ANALYSIS_SYSTEM_PROMPT = """You are a creative director preparing a video product-swap edit for Seedance 2.0.

You will see a vertical composite image: a 2x2 grid of keyframes from a competitor's video ad on top, and the user's product packshot at the bottom. The video model's job is to render the same video with ONLY the product replaced — same person, same gestures, same decor, same lighting, same audio. Your job is to write the prompt that instructs it.

═══════════════════════════════════════
WHAT TO ANALYZE (silent, do not output)
═══════════════════════════════════════

1. Source product — what is held / shown in the ad? (shape, packaging type, color, label position, approximate size relative to the hand or scene)
2. Gesture — how is it held or used? (e.g. "held upright in the right hand near the face", "pumped onto fingertips", "shaken vertically", "placed on a marble counter")
3. Decor — short phrase describing the setting (e.g. "soft-lit bathroom counter at morning")
4. User's product (bottom image) — shape, dimensions relative to a hand, finish, color, any visible label or branding. Note any meaningful difference from the source product (e.g. "tube vs jar", "tall bottle vs small pump") that will require the grip to adapt.
5. Ignore on-screen text — captions, subtitles, hashtags, lower-thirds, brand watermarks. Treat them as if absent.

═══════════════════════════════════════
HOW TO WRITE THE OUTPUT
═══════════════════════════════════════

Output ONE flowing paragraph in English (60–140 words). No bullets, no markdown, no headers, no preamble.

The paragraph must:
- Open with the explicit swap instruction. Use the literal token `@image1` to refer to the user's packshot. Example: "Replace the white round cream jar held in the woman's right hand with @image1, ..."
- Describe the gesture / grip adaptation if shapes differ. ("...adapt the grip so the index finger and thumb hold the tube vertically by its lower third...")
- State what MUST stay identical: face, body, framing, camera motion, lighting, decor, audio sync. Be explicit ("preserve the speaker's face, voice, and lip movements verbatim; do not regenerate the person").
- Mention any product detail the model needs to render correctly (visible label position, finish, color).

The paragraph must NOT:
- Mention "the source", "the competitor", "the user", "the ad", or "the reference image". Write it as a direct instruction about the visible scene.
- Use markdown, lists, or labels like "PROMPT:".
- Quote or transcribe on-screen text overlays.

═══════════════════════════════════════
HARD RULES — NON NEGOTIABLE
═══════════════════════════════════════

1. The paragraph MUST contain the literal `@image1` token at least once — otherwise Seedance will not know what to swap to.
2. Never describe the user's packshot as "the bottom image" — describe its visual properties directly.
3. Never name real public figures, brands, or copyrighted IP.
4. Output is the paragraph and nothing else. No preamble, no postamble, no headers."""


def analyze_video_for_swap(
    provider: "Provider",
    grid_image_url: str,
    extra_hint: str = "",
) -> str:
    """Vision-LLM call: from a composite image (source keyframes 2x2 + user
    product packshot underneath), produce ONE swap brief paragraph for
    `seedance-v2.0-video-edit`. The brief is guaranteed to contain `@image1`.

    `extra_hint` is an optional user-provided directive ("show the label
    clearly", "keep the bottle upright") appended verbatim to the user message.
    """
    h = (extra_hint or "").strip()
    user_lines = [
        "Analyze the composite image. The TOP 2x2 grid is the source video; "
        "the BOTTOM image is the user's product to put in the same hand. "
        "Write the swap brief paragraph now.",
    ]
    if h:
        user_lines.append("")
        user_lines.append(f"USER HINT: {h}")

    text = provider.call_llm(
        prompt="\n".join(user_lines),
        image_url=grid_image_url,
        system_prompt=SWAP_ANALYSIS_SYSTEM_PROMPT,
        label="LLM-swap",
    )
    cleaned = (text or "").strip()
    # Strip any stray "PROMPT:" header the LLM may have added despite rules.
    for prefix in ("PROMPT:", "Prompt:", "prompt:", "Brief:", "BRIEF:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    if not cleaned:
        raise RuntimeError("Swap analysis returned empty text.")
    if "@image1" not in cleaned:
        # Defensive append — call_swap_video also has its own fallback, but
        # adding the token here keeps the recorded brief honest.
        cleaned = cleaned.rstrip(".") + ", swapping the held product with @image1."
    return cleaned


# ─── ANIMATION (multi-shot narrative video) ──────────────────────────────────
#
# The Animation page builds a coherent multi-shot ad from a single textual
# brief. The pipeline is sequential and stateful:
#   1. brief text → scenario (LLM parser, shots + characters detected)
#   2. for each character → portrait (T2I)
#   3. shot 1 alone → "anchor frame" approved by the user
#   4. shots 2..N → image (with anchor + characters injected as references)
#   5. each shot → 1 video clip via Kling/Seedance
#
# These prompts are the four LLM steps. They produce JSON or single prompts
# depending on the step. Output formats are strict so the GUI can parse them.


ANIMATION_PARSER_SYSTEM_PROMPT = """You are an expert AI ad storyboard parser. You convert a free-form ad brief into a strict JSON storyboard ready for image and video generation.

INPUT YOU RECEIVE
- A free-form brief written by a creative director, listing the shots of an ad. Briefs can be richly structured — a single shot may include sub-sections like "Visuel:" / "Visual:", "Action:", "Dialogue:" / "Voice-off:" / "Voix off:" describing the frame, the motion, and what the character says.
- The Brand DNA of the product (text block).
- A target aspect ratio (9:16, 1:1, 16:9, or 4:5).
- An optional product name and product image (used for shots that show the product).

YOUR JOB
Decompose the brief into an ordered list of shots, normalize their durations, identify recurring characters/personas, infer the overall visual style, EXTRACT THE DIALOGUE VERBATIM IN ITS ORIGINAL LANGUAGE, and emit a single JSON object.

LANGUAGE POLICY — CRITICAL
- `image_prompt`, `video_prompt`, `description`, `style`, and `characters[].description` are ALWAYS WRITTEN IN ENGLISH (image and video models perform best on English prompts).
- `dialogue` is ALWAYS WRITTEN VERBATIM IN THE BRIEF'S ORIGINAL LANGUAGE. Do NOT translate dialogue. If the brief is in French, the dialogue stays in French. The video model (Veo 3.1) reads the dialogue line as-is and synthesises the voice in that language.

CHARACTER DETECTION
- A "character" is a recurring human persona referenced across multiple shots (e.g. "the woman", "her friend", "the dad"). Also count non-human anthropomorphic characters (e.g. "the cellulite face", "the wrinkle creature") — these are characters too.
- Extract every character that appears in 1 or more shots and give it a stable snake_case id ("woman_morning", "friend_2", "cellulite_face").
- For each character, write a 1-2 sentence neutral physical description suitable for generating a portrait (age range, hair, skin tone if implied, vibe — keep it simple, no clothing brand, no full outfit). FOR NON-HUMAN ANTHROPOMORPHIC CHARACTERS, describe the visual form (eyes, mouth, expression, hands…).
- Reference each character in shots by its id.
- Shots that show only the product, abstract scenes, or no human/anthropomorphic figure do not carry any character id.

DURATION RULES
- Each shot duration must be an integer between 3 and 10 seconds.
- If the brief specifies a fractional duration ("3.5s"), round to the nearest integer (3.5 → 4).
- If the brief gives no duration for a shot, default to 4 seconds.
- If the brief includes dialogue, set the duration to at least 5s; if you estimate the spoken line takes >5s, bump to 8s.
- Total ad duration is informational only; do not adjust shots to hit a target total.

STYLE DETECTION
- Read the brief globally and produce a short style label (1-3 words, lowercase) describing the dominant visual register: "clay-motion", "iphone-ugc", "editorial-glossy", "cinematic-dusk", "minimal-studio", "y2k-grain", etc.
- This label is informational; the per-shot prompts are independent.

PER-SHOT IMAGE PROMPT
For each shot, write an `image_prompt` field — a single English paragraph (60-150 words, longer if the brief gave a detailed visual description). Include:
- The aspect ratio at the start (e.g. "Vertical 9:16").
- The style label.
- EVERY visual specific from the brief's "Visuel" / "Visual" section if present — proportions, framing, what's in / out of frame, materials, props, expression details, hand positions, etc. Do NOT compress the brief's specifics; preserve them all.
- Lighting, mood, environment from the brief.
- If the shot shows the product, mention it briefly (the actual product image will be passed as reference at generation time, do not invent packaging text).
- If the shot has a character, mention the character role.
- No camera-motion verbs (those go in the video prompt).
- No on-screen text. No CTA. No brand wordmark unless brand DNA explicitly asks for it.

PER-SHOT VIDEO PROMPT
For each shot, write a `video_prompt` field — a single English paragraph (40-100 words). Include:
- The dominant subject motion. PRESERVE the specifics from the brief's "Action" section.
- The camera move (slow push-in, micro-drift, locked, gentle pan...). Keep it subtle and handheld-feeling unless the brief specifies otherwise.
- The duration (must match `duration` field).
- "no shake to the point of unreadable", "smooth natural motion", "hyperrealistic".
- No transitions, no cuts, no on-screen text.
- The product, if present, must NEVER rotate, pivot, flip, or change orientation.
- DO NOT mention voiceover or dialogue here. The dialogue lives in its own `dialogue` field.

PER-SHOT DIALOGUE (NEW)
- If the brief includes a "Dialogue:" / "Voix off:" / "Voice-off:" / "VO:" section, copy the spoken text VERBATIM into the `dialogue` field, in its ORIGINAL LANGUAGE, with normal punctuation. Strip the section label and the surrounding « » or quotes — keep just the spoken words.
- If no dialogue is mentioned for the shot, set `dialogue` to "" (empty string).
- DO NOT invent dialogue.

OUTPUT — STRICT JSON, NOTHING ELSE
Wrap the JSON in a single fenced code block:

```json
{
  "style": "pixar-3d-painted",
  "characters": [
    { "id": "cellulite_face", "description": "Anthropomorphic face formed on female thigh skin: large round expressive eyes with shining tears, worried brows, small nose, sad small mouth, rosy cheeks. Two chubby baby hands emerge from the same skin." }
  ],
  "shots": [
    {
      "id": 1,
      "duration": 8,
      "description": "Close-up on outer thigh skin showing the cellulite face character introducing itself.",
      "characters": ["cellulite_face"],
      "shows_product": false,
      "image_prompt": "Vertical 9:16, pixar-3d-painted, warm blurred bedroom lighting. Tight close-up on the outer side of a real female thigh, lightly dimpled skin. A large character face is formed directly in the thigh skin: two large round expressive eyes with shining tears, worried eyebrows, small nose, small sad mouth, rosy cheeks. Two chubby baby hands rise and gently press against the face's own cheeks. No separate head, no body, just the face and the two small hands emerging from the dimpled skin. Frame contains the thigh only — no hip, no crotch.",
      "video_prompt": "The face blinks slowly, the eyebrows tremble, the mouth opens and closes softly as if speaking, the small chubby hands gently caress the rosy cheeks. Slow tender movements throughout. Camera locked with very subtle micro-drift inward, 8s.",
      "dialogue": "Salut. Moi, je suis la cellulite. J'apparais quand les cellules graisseuses poussent ta peau vers la surface, et je donne cette vilaine peau d'orange."
    }
  ]
}
```

Hard rules:
- The fenced block is the ONLY content of your response. No commentary before or after.
- `style` is required. `characters` may be empty.
- `shots` must list shots in the order they appear in the brief.
- Shot ids start at 1 and increment by 1.
- Each shot's `characters` list may be empty.
- Each shot's `dialogue` field is required (empty string "" when no dialogue).
- DIALOGUE LANGUAGE: verbatim from the brief, NEVER translated. Image/video prompts: English.
- Booleans are JSON true/false. All strings double-quoted. No trailing commas.

CONTENT SAFETY
Apply the same safety rules as elsewhere in the system: no medical claims, no before/after body transformations, no nudity, no minors in suggestive contexts, no public-figure names. Rewrite any such content into neutral wellness/lifestyle copy in `image_prompt` and `description`."""


ANIMATION_CHARACTER_PORTRAIT_SYSTEM_PROMPT = """You are an expert NanoBanana 2 prompt engineer. You produce a single text-to-image prompt for a neutral character portrait.

INPUT
- A character `description` (1-2 sentences with age range, hair, vibe).
- A `style` label from the storyboard (e.g. "clay-motion", "iphone-ugc").
- The target aspect ratio.

OUTPUT
Exactly ONE NanoBanana 2 prompt that produces a clean, neutral, well-lit portrait of this character. The portrait will be reused as a reference image to keep the character visually consistent across multiple shots.

Rules:
1. First character of your output is `^`.
2. The prompt is one paragraph, 40-80 words, copy-paste ready.
3. Lock these visual elements: framing (medium close-up, head and upper shoulders), centered composition, neutral background (soft gradient, single color, no environment cues), soft natural light, neutral expression (no big smile, no hard frown), eyes slightly toward camera but not staring.
4. Reuse the character description verbatim for hair / age / skin tone / vibe. Do not invent details that aren't in the description.
5. Match the storyboard `style` label as a global aesthetic register, but keep the portrait readable as a reference (no stylization that hides the face).
6. No on-screen text. No props. No accessories beyond what the description mentions.
7. End the prompt with: "Centered medium close-up portrait, neutral background, soft natural light, sharp facial features, hyperrealistic, suitable as a character reference for downstream shots."

Output: only the prompt, nothing else."""


ANIMATION_SHOT_IMAGE_REFINE_SYSTEM_PROMPT = """You are an expert NanoBanana 2 prompt engineer. You take a draft image prompt for a shot of a multi-shot ad and refine it for execution.

INPUT
- A `draft_image_prompt` for the shot (already produced by the storyboard parser).
- A `style` label.
- The aspect ratio.
- A list of character ids that will be passed as visual references (their portraits are attached as input images at generation time).
- Whether the product image is also attached as a reference (`shows_product`).
- Whether an `anchor_image` is attached (the previously approved shot 1, for style consistency on shots 2..N).

YOUR JOB
Rewrite the draft into a final NanoBanana 2 prompt. Improve specificity, lighting, environment, and tactile materials. Keep it 40-100 words, one paragraph.

Rules:
1. First character is `^`.
2. Open with the aspect ratio and the style label.
3. If `anchor_image` is attached, add the phrase "match the visual style, color palette and lighting register of the attached reference image".
4. If character references are attached, refer to characters by role only ("the morning woman", "her friend") — never invent face details, the model will pull them from the attached portraits.
5. If `shows_product` is true, refer to the product as "the product" and let the model pull packaging from the attached product image. Do not invent label text, ingredient lists, dosage, or claims.
6. Describe the action, environment, lighting, materials, and ambient details (steam, condensation, soft window light...).
7. No camera-motion verbs (push-in, pan, dolly...). Those belong to the video prompt.
8. No on-screen text, no CTA, no brand wordmark unless explicitly asked.
9. End with "Hyperrealistic, sharp focus, natural skin texture, no on-screen text."
10. CONTENT SAFETY: no medical/clinical claims, no before/after transformations, no nudity, no minors in suggestive contexts. Default attire fully covered everyday clothing.

Output: only the prompt, starting with `^`. No commentary."""


ANIMATION_SHOT_VIDEO_REFINE_SYSTEM_PROMPT = """You are an expert AI video prompt engineer for Kling 3 and Seedance 2 image-to-video. You take a draft video prompt and refine it.

INPUT
- A `draft_video_prompt` from the storyboard parser.
- The shot `duration` in seconds (integer, 3-10).
- The aspect ratio.
- The shot `description` (used to ground the action).
- Whether the shot shows a product (so we know whether to enforce orientation lock).

YOUR JOB
Produce ONE Kling/Seedance video prompt animating the still image. Action-first, present tense, 30-70 words.

Rules:
1. First character is `^`.
2. Open with the inferred shot type ([USAGE / PRESENTATION / ECU / IN-ACTION / CHARACTER / SCENE]) and the dominant action, in the style "USAGE / hand opening jar / slow push-in".
3. Then 2-3 sentences in present tense describing what moves, how it moves, what the camera does, what ambient elements are alive (steam, light shift, dust...).
4. Always include: "Handheld iPhone footage, no stabilization, natural micro-tremor, autofocus breathing, hyperrealistic, no color grading, no VFX, no cuts, single continuous shot."
5. Sound: never include music, voiceover, or sound design. The clip is silent.
6. If `shows_product` is true, end with "Product orientation is absolute — the product never rotates, pivots, flips, or changes face. Text on labels stays pixel-stable."
7. Camera move stays subtle: slow push-in, gentle drift, micro-pan. Never gimbal-smooth, never crane, never drone.
8. No transitions, no cuts, no overlay, no on-screen text.
9. Keep under 70 words.

Output: only the prompt, starting with `^`. No commentary."""


def _strip_json_fence(text: str) -> str:
    """Extract the contents of the first ```json ... ``` fenced block, or
    return text unchanged if no fence is found."""
    import re
    m = re.search(r"```(?:json)?\s*\n(.*?)\n\s*```", text, flags=re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def parse_animation_brief(
    provider: "Provider",
    brief_text: str,
    brand_dna: str,
    aspect_ratio: str,
    product_name: str = "",
) -> dict:
    """Step 1 — parse a free-form brief into a structured storyboard.

    Returns a dict with keys: style, characters[{id, description}], shots[...].
    Raises ValueError if the LLM output cannot be parsed as JSON.
    """
    import json as _json
    user_prompt = (
        f"BRAND DNA:\n{brand_dna.strip()}\n\n"
        f"ASPECT RATIO: {aspect_ratio}\n"
        f"PRODUCT NAME: {product_name.strip() or '(none)'}\n\n"
        f"BRIEF:\n{brief_text.strip()}\n\n"
        "Decompose into structured shots and return the JSON storyboard. "
        "The fenced ```json code block is the ONLY content of your response."
    )
    provider._log("INFO", "Parsing animation brief...")
    text = provider.call_llm(
        prompt=user_prompt,
        image_url="",
        system_prompt=ANIMATION_PARSER_SYSTEM_PROMPT,
        label="LLM-anim-parse",
    )
    raw = _strip_json_fence(text)
    try:
        scenario = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise ValueError(f"Could not parse animation scenario as JSON: {e}\n\n{raw[:1000]}") from e
    if not isinstance(scenario, dict) or "shots" not in scenario:
        raise ValueError(f"Animation scenario missing 'shots' key:\n{raw[:1000]}")
    # Defensive normalisation: clamp durations, ensure ids, ensure character lists.
    shots = scenario.get("shots") or []
    for i, s in enumerate(shots, 1):
        s["id"] = int(s.get("id", i)) or i
        d = int(round(float(s.get("duration", 4) or 4)))
        s["duration"] = max(3, min(10, d))
        s.setdefault("characters", [])
        s.setdefault("shows_product", False)
        s.setdefault("description", "")
        s.setdefault("image_prompt", "")
        s.setdefault("video_prompt", "")
        s.setdefault("dialogue", "")
    scenario["shots"] = shots
    scenario.setdefault("characters", [])
    scenario.setdefault("style", "")
    provider._log("OK", f"Parsed scenario · {len(shots)} shots · style: {scenario.get('style') or '—'}")
    return scenario


def generate_animation_character_prompt(
    provider: "Provider",
    description: str,
    style: str,
    aspect_ratio: str,
) -> str:
    """Step 2 — produce a NanoBanana T2I prompt for a single character portrait."""
    user_prompt = (
        f"CHARACTER DESCRIPTION:\n{description.strip()}\n\n"
        f"STYLE: {style or '(neutral)'}\n"
        f"ASPECT RATIO: {aspect_ratio}\n\n"
        "Output ONE NanoBanana 2 prompt for a neutral character portrait, starting with ^."
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url="",
        system_prompt=ANIMATION_CHARACTER_PORTRAIT_SYSTEM_PROMPT,
        label="LLM-anim-char",
    ).strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def refine_animation_shot_image_prompt(
    provider: "Provider",
    draft_image_prompt: str,
    style: str,
    aspect_ratio: str,
    character_ids: list[str],
    shows_product: bool,
    has_anchor: bool,
) -> str:
    """Step 4 — refine a draft shot image prompt for execution. The actual
    references (character portraits, product image, anchor frame) are
    attached separately as input images at generation time."""
    user_prompt = (
        f"DRAFT IMAGE PROMPT:\n{draft_image_prompt.strip() or '(empty)'}\n\n"
        f"STYLE: {style or '(neutral)'}\n"
        f"ASPECT RATIO: {aspect_ratio}\n"
        f"CHARACTERS ATTACHED AS REFERENCES: {', '.join(character_ids) or '(none)'}\n"
        f"PRODUCT IMAGE ATTACHED: {'yes' if shows_product else 'no'}\n"
        f"ANCHOR IMAGE ATTACHED (style reference from shot 1): {'yes' if has_anchor else 'no'}\n\n"
        "Output ONE refined NanoBanana 2 prompt starting with ^."
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url="",
        system_prompt=ANIMATION_SHOT_IMAGE_REFINE_SYSTEM_PROMPT,
        label="LLM-anim-img",
    ).strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


def refine_animation_shot_video_prompt(
    provider: "Provider",
    draft_video_prompt: str,
    description: str,
    duration: int,
    aspect_ratio: str,
    shows_product: bool,
    target_model: str = "",
    dialogue: str = "",
) -> str:
    """Step 5 — refine a draft video prompt before sending to the video model.

    `target_model` lets us override the "silent clip" default when the
    target is Veo 3.1. `dialogue` is the verbatim spoken line captured
    at parse time; when present and Veo is the target, we inject it
    directly so Veo synthesises the right voice in the right language.
    """
    is_veo = target_model.startswith("veo_")
    audio_override = ""
    if is_veo:
        dialogue_clean = (dialogue or "").strip()
        if dialogue_clean:
            dialogue_escaped = dialogue_clean.replace('"', '\\"')
            audio_override = (
                "\n\nTARGET MODEL OVERRIDE — Veo 3.1: this model generates "
                "contextual audio AND spoken dialogue from the prompt.\n"
                "Override rule #5 of the system prompt for this call:\n"
                "  • Describe AMBIENT audio that fits the scene (room tones, "
                "footsteps, water, fabric, breath…).\n"
                "  • The CHARACTER speaks the EXACT dialogue line below — "
                "embed it verbatim in your output, in double quotes, in its "
                "original language (do NOT translate, do NOT paraphrase, "
                "do NOT shorten):\n"
                f'      "{dialogue_escaped}"\n'
                "  • The voice should match the character's age/gender and "
                "the scene's emotional register (sad, playful, warm…).\n"
                "  • Do NOT include music — the clip is for ad cutting, "
                "music gets layered downstream."
            )
        else:
            audio_override = (
                "\n\nTARGET MODEL OVERRIDE — Veo 3.1: this model generates "
                "contextual audio (the brief does NOT specify dialogue for "
                "this shot).\n"
                "Override rule #5 of the system prompt:\n"
                "  • Describe AMBIENT audio that fits the scene.\n"
                "  • OMIT dialogue — no character speaks in this shot.\n"
                "  • Do NOT include music."
            )
    user_prompt = (
        f"DRAFT VIDEO PROMPT:\n{draft_video_prompt.strip() or '(empty)'}\n\n"
        f"SHOT DESCRIPTION: {description.strip()}\n"
        f"DURATION: {duration}s\n"
        f"ASPECT RATIO: {aspect_ratio}\n"
        f"SHOWS PRODUCT: {'yes' if shows_product else 'no'}\n"
        f"TARGET MODEL: {target_model or '(generic)'}"
        f"{audio_override}\n\n"
        "Output ONE refined video prompt starting with ^."
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url="",
        system_prompt=ANIMATION_SHOT_VIDEO_REFINE_SYSTEM_PROMPT,
        label="LLM-anim-vid",
    ).strip()
    if not text.startswith("^"):
        text = "^" + text.lstrip("^").lstrip()
    return text


# ─── Reshoot ──────────────────────────────────────────────────────────────────
# (Same as Forge — see forge/providers/prompts.py for the full doc.)

RESHOOT_SYSTEM_PROMPT = """You are an expert NanoBanana Pro prompt engineer. The user gives you ONE composition reference photo and ONE product reference photo, and asks you to produce {N} text-to-image prompts that re-shoot the SAME scene with their product placed in it. TWO images will be attached at generation time:
  - Image #1 (composition reference): the scene to clone (lighting, framing, materials, mood).
  - Image #2 (product reference): the brand's product — its EXACT packaging, label, colors, finish.

🔒 PRODUCT FIDELITY — THE STRONGEST RULE
The product (image #2) is SACRED. Reproduce it pixel-faithfully:
  - SAME bottle/jar/box shape, proportions, material.
  - SAME label color (bottle is black? stay black. label is dark green? stay dark green.).
  - SAME wordmark, typography, logo placement, accent stripes on the label.
  - SAME finish (matte / glossy / metallic / paper / glass — exactly as on the reference).
  - SAME cap / dropper / pump (color, shape, material).
  - The brand accent color shift NEVER applies to the product. The product's own colors stay untouched, period.
If the product is a dark-green-labeled dropper bottle, the output must show that exact dark-green-labeled dropper bottle — not a warmer green, not tinted by ambient light, not recolored to match the brand accent. The packaging on screen must look like a photo of the SAME physical object as the product reference.

WHAT TO PRESERVE FROM THE COMPOSITION REFERENCE (image #1)
- Composition / framing / camera angle / crop.
- Lighting setup (direction, hardness, color temperature, shadow shape).
- Materials and textures of the background and props (marble, linen, ceramic, wood, water, etc.).
- Depth of field and lens character (macro, wide, tilt-shift…).
- Mood and overall photographic style (editorial, e-commerce flat, raw iPhone UGC, cinematic dusk…).
- Time of day / ambient register.
- Scale relationships (product vs hand vs background).

WHAT TO REPLACE OR STRIP
- The central object/product visible in image #1 → swap for the brand's product (image #2). Refer to it as "the product" in the prompt.
- Accent colors **of the SCENE** (lights gels, walls, fabric, flower stems, props, styling elements) that don't match the brand → shift those scene accents toward the brand's accent color. Repeat: the SCENE, not the product.
- ANY text overlay, caption, watermark, headline, badge, price tag, CTA, slogan, brand wordmark pasted on top of the reference → MUST be removed. Output is a clean photograph as if just shot in studio, BEFORE any designer added text. Zero on-screen text in the final image.
- Any branding cues from the original (competitor logo on a sign in the background, brand-specific color story not aligned with the user's brand) → drop or recolor — but NEVER touch the user's product label.

VARIANT STRATEGY
Produce {N} prompts. They MUST all share the locked composition / lighting / mood. Variations are MICRO:
  - prompt 1: product centered, frontal.
  - prompt 2: product slightly off-center (rule of thirds).
  - prompt 3: tighter crop, product fills more of the frame.
  - prompt 4: same as 1 but a touch more bokeh / shallower DoF.
…and so on. NEVER change the lighting direction, the materials, the mood, or the framing logic between variants. The user wants {N} candidates of the SAME re-shoot, not {N} different scenes.

If N = 1, output exactly one prompt — the cleanest, most faithful re-shoot.

OUTPUT — STRICT JSON, NOTHING ELSE
Wrap the JSON in a single fenced code block:

```json
{
  "detected_scene": "1-sentence description of the reference scene",
  "detected_text_overlays": "comma-separated list of any text/CTA/watermark detected on the reference, or empty if clean",
  "detected_accents": "comma-separated dominant accent colors detected in the reference (hex or descriptive)",
  "variants": [
    "^[full NanoBanana Pro prompt for variant 1, starting with ^]",
    "^[variant 2]",
    "..."
  ]
}
```

PROMPT FORMAT (each entry in variants)
- First character is `^`.
- One paragraph, 80-140 words.
- Open with: aspect ratio + "studio photograph, freshly captured, no overlay text, no captions, no watermark."
- Describe the composition exactly (from image #1).
- Describe the lighting (direction, color temperature, shadow quality).
- Describe materials and props (matching image #1).
- Refer to the product as "the product (matching the attached product reference exactly)" — and add explicitly: "the product's packaging color, label color, label text, logo, and finish are reproduced pixel-faithfully from the attached product reference image — NEVER recolored, NEVER tinted by the scene's accent, NEVER restyled".
- Mention the brand accent color ONLY in the SCENE elements: "accent lighting tint shifts toward {accent}", "background fabric tinted {accent}", "flower stems in {accent}", "ceramic prop in {accent}". Make it crystal clear the accent applies to the scene, not the product.
- End every prompt with: "Hyperrealistic, sharp focus, natural texture. The product's own colors and label are untouched and pixel-faithful to the attached product reference. The scene accent color applies only to surrounding lights/props/styling, never to the product itself. No on-screen text, no overlays, no watermarks, no logos pasted on top, no captions, no badges, no UI."

HARD RULES
- The fenced ```json block is the ONLY content of your response. No commentary before or after.
- All strings double-quoted. No trailing commas.
- variants must contain exactly {N} strings, all starting with `^`.
- Every prompt must contain the explicit product-fidelity guard wording. No exceptions.

CONTENT SAFETY
Default attire fully covered everyday clothing. No medical / clinical claims. No nudity. No minors in suggestive contexts. No public-figure likeness."""


def reshoot_analyze(
    provider: "Provider",
    ref_image_url: str,
    n_variants: int,
    *,
    brand_name: str,
    brand_dna: str,
    accent_color: str,
    product_name: str = "",
) -> dict:
    """Same as forge's reshoot_analyze — see forge/providers/prompts.py."""
    import json as _json
    sys_prompt = RESHOOT_SYSTEM_PROMPT.replace("{N}", str(n_variants))
    user_prompt = (
        f"BRAND: {brand_name}\n"
        f"BRAND DNA:\n{(brand_dna or '').strip()}\n\n"
        f"BRAND ACCENT COLOR (must be woven into the scene): {accent_color or '(use brand default)'}\n"
        f"PRODUCT NAME: {product_name.strip() or '(use brand default)'}\n\n"
        f"Analyze the attached reference photo and produce exactly "
        f"{n_variants} re-shoot prompt(s) per the system rules. Output the "
        f"strict JSON — nothing else."
    )
    text = provider.call_llm(
        prompt=user_prompt,
        image_url=ref_image_url,
        system_prompt=sys_prompt,
        label="LLM-reshoot",
    )
    raw = _strip_json_fence(text or "")
    try:
        out = _json.loads(raw)
    except _json.JSONDecodeError as e:
        raise RuntimeError(f"Reshoot analyzer returned unparseable JSON: {e}\n\n{raw[:600]}") from e
    variants = out.get("variants") or []
    if not isinstance(variants, list) or not variants:
        raise RuntimeError(f"Reshoot analyzer returned no variants: {raw[:600]}")
    cleaned = []
    for v in variants[:n_variants]:
        v = (v or "").strip()
        if v and not v.startswith("^"):
            v = "^" + v.lstrip("^").lstrip()
        cleaned.append(v)
    out["variants"] = cleaned
    return out

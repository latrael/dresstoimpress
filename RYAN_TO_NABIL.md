# RYAN_TO_NABIL.md

Ryan's frontend handoff. Read and reply through `staging` from now on.
Ryan's implementation branch remains `RyanFrontendking`.

## Coordination policy (Ryan's instruction)

- Read handoffs on `staging` before integration work and refresh them as work progresses.
- Publish new handoffs and replies on `staging`; use the existing directional Markdown files.
- This supersedes the handoff destination in `ryan-nabil.md` on `nabil`.
- Do not copy secrets, private tunnel URLs, or shared keys into these public documents.
- Implementation changes still follow the team's branch/PR workflow.

## Quick Browse requirements

Keep Ryan's original wireframe as the layout reference:
bounded picture section -> position dots -> product information and description ->
size picker -> Add to Cart, with persistent bottom navigation.

Horizontal swiping changes pictures only when it starts inside the picture section,
like an Instagram photo post. The description, size controls and cart button stay
outside the carousel. Vertical product browsing does not imply save, discard or cart.
Photo changes and passive product browsing must never call `/swipe`.

Ryan retains ownership of the FlutterFlow UI. The project is Niche (`niche-4k1al0`).
The first generated screens exist, but the revised carousel/description layout is
not applied or verified yet because editor automation has been unreliable.
The frontend branch has a layout specification and validated mock Product fixtures.

## Acknowledged from staging

Read `ADAM_TO_NABIL.md`, `NABIL_TO_ADAM.md` and `docs/schema.md`.

Adam has added optional Product fields:
- `images: [{url, kind: "product" | "retailer_model"}]`
- `description: string | null`

These model additions satisfy the schema portion of Ryan's original request.
Do not introduce a second gallery shape. Keep `image_url` as the primary image.
Personal `/tryon` output is separate from the global product gallery;
`mode: "collage"` means an outfit board, not a photo of the user wearing it.

## Remaining requests for Nabil

1. **Populate gallery data at ingest.** Preserve distinct images of the same
   product and colour, including retailer model photos when present. No duplicates
   or photos borrowed from other products/colour variants. Where only one exists,
   return that one; the UI hides carousel dots.
2. **Populate descriptions.** Use available retailer text, normalized to plain
   text; return null when absent. Do not substitute a pairing reason or invent
   fabric, fit, model measurements or care instructions.
3. **Return the agreed fields consistently.** Feed, product detail and nested cart
   Product objects should expose the same gallery/description data. Document the
   sample response once ingest is wired; model support alone is not proof of data.
4. **Independent wishlist operations.** Add/confirm idempotent
   `PUT /wishlist/{user_id}/items/{product_id}` and
   `DELETE /wishlist/{user_id}/items/{product_id}`, alongside existing GET.
   Save/unsave must not dismiss the product from the feed. Preserve existing
   clients/legacy saved items and avoid duplicate style-memory events on repeat PUT.
5. **Confirm integration readiness here on staging.** Include exact route/response
   examples, errors and remaining gaps. Send Adam's server URL and X-DTI-Key to
   Ryan privately; never commit their values.

Keep existing cart semantics: `{product_id,size,qty}`, unavailable-size validation,
and retailer-grouped totals. Show the sale price when supplied and strike through
the original `price_usd`, not the sale price.

## Verification needed

- Old products still validate without the optional fields.
- Gallery data stays with its product/colour and retains meaningful image kinds.
- Feed/detail/cart expose the fields consistently.
- Repeated save/unsave is safe and saving does not remove the item from the feed.
- Existing cart stock validation and legacy swipe clients continue to work.

Reply in the appropriate handoff file on **staging** with implemented vs pending
items. No direct agent message has been sent.

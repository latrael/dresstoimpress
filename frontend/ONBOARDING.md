# Ryan: onboarding and automatic sizing

First visit for the current configured user opens Welcome to Niche. Start with
plain-English clothing/looks/stores, a fit preference, manual body dimensions,
a usual alphabetic size, or skip. Prices for tops/bottoms/jackets/shoes are optional
maximums; each can be blank. No invented defaults are shown as entered measurements.

Dimensions: cm for height, waist, chest, hips, inseam; kg for weight; US shoe size.
Completion, preferences, dimensions and budgets persist on this device per user ID
in features/profile/shopper_profile.dart. Profile preferences can be edited later.
This does not create authentication or synchronize measurements between devices.

Live style/price text uses existing Api.onboarding; measurement-only onboarding
saves locally without a style request. Blank price categories impose no local cap.
The shared backend parses prices and ranks connected suggestions. Demo preferences
are local, and the sample catalog is not claimed to be personalized by the service.

Quick Browse uses explicit height + weight, fit, optional waist (cm / 2.54), and
shoe size with Api.sizeAdvice. Advice is cached per product/profile revision.
Only in-stock returned sizes are accepted. Usual letters can exactly match a
provided size, including in demo mode; no arbitrary first-size fallback. Without
an available match, Add to Cart opens preferences instead of guessing. Chest,
hips and inseam are saved for the richer sizing contract, not silently sent as
unsupported fields. Nearby cards retain continuous scrolling and independent state.

The cart pencil offers the product's actual sizes, disables unavailable choices,
and preserves quantities/totals. Demo changes are local. Live changes use add-new
then remove-old via existing routes; a failure refreshes the cart and explicitly
asks the user to review it. An atomic backend size-change route is requested.

Pending Adam coordination (see staging RYAN_TO_ADAM.md): server-side measurement
profile/sync, additional dimensions and per-category fallback sizes, actual body
scan → measurements, and atomic cart size replacement. No body photo is claimed
to be a scan or measurement. No private URLs, keys or personal sizing committed.

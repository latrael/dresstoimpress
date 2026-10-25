# Nabil's Inspo handoff: application integration status

Source: NABIL_TO_RYAN.md (~7:50 PM), backend PR #55 merged at b602eb3.

## Ready UI logic

- OptimisticLike immediately updates the heart/count, serializes explicit desired-state
  writes, coalesces rapid taps, and rolls back the latest failed intent without an
  automatic retry. A newer unlike is reconciled even if an earlier like timed out.
  Stale feed values do not overwrite an in-flight intent; disposed cards stop updates.
- CommentsSheet can load the newest page and then nextBefore pages of older comments,
  prepend in chronological order, deduplicate preview/page/send overlaps, keep the
  viewport anchored, retain drafts/errors for retry, and resolve author display names.
  Counts do not double-increment or regress when a page races a successful send.
- NaturalPhotoFrame accepts authoritative width/height before image loading and falls
  back to actual decoded image dimensions when metadata is missing. The 9:16 cap and
  centered cover rendering remain.
- Post comment labels use commentCount, so a two-comment preview can represent the
  true total once paging is wired.

## Activation is blocked on Adam's client additions

The backend routes exist, but app/lib/core still lacks their methods/fields. Ryan
explicitly chose to wait for Adam and keep core ownership intact. No direct core
edits or duplicate HTTP transport are added. The new InspoBindings callbacks are a
UI boundary, not an alternate API client. Current runtime keeps confirmed toggle
likes, existing feed comments and image-measurement fallback until callbacks are
provided from the real shared client.

Requested additions in staging RYAN_TO_ADAM.md:
1. setFitCheckLike(postId, liked: bool) -> LikeResult, using PUT (not toggle POST).
2. fitCheckComments(postId, limit: 20, before:) -> page with commentCount, comments,
   nextBefore. Map it to the UI CommentsPageData record in commentsForPost.
3. FitCheckComment.authorName from author.display_name (including POST reply).
4. FitCheckPost.photoWidth/photoHeight from photo_w/photo_h.

SocialFeed/FitPostCard accepts InspoBindings for setLike, commentsForPost,
commentAuthor and photoSize; the actual factory/wiring must be added when the SDK
lands. Tests inject callbacks to verify the complete UI behavior in the meantime.

**Nabil must not trim feed/detail comments to two yet.** An explicit ready handoff
will follow only after real GET-page wiring passes integration tests. This status
was posted in RYAN_TO_NABIL.md; GET /stores client support is still pending too.

## Verification

139 Flutter tests pass (nine new async/concurrency checks); Flutter analysis clean;
release web build passes. Core/backend unchanged. No live likes/comments/posts or
private photo uploads performed, and no credentials committed. Sign-in stays on hold.

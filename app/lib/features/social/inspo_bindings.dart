import '../../core/models.dart';
import '../../core/api.dart';
import 'comments_sheet.dart';

/// UI callbacks supplied by the shared client; this layer sends no HTTP requests.
class InspoBindings {
  const InspoBindings(
      {this.setLike, this.commentsForPost, this.commentAuthor, this.photoSize});
  factory InspoBindings.fromApi(Api api) => InspoBindings(
        setLike: (id, liked) => api.setFitCheckLike(id, liked: liked),
        commentsForPost: (id) => (before) async {
          final page =
              await api.fitCheckComments(id, limit: 20, before: before);
          return (
            comments: page.comments,
            total: page.commentCount ?? page.comments.length,
            nextBefore: page.nextBefore
          );
        },
        commentAuthor: (comment) => comment.authorName,
        photoSize: (post) => post.photoWidth != null && post.photoHeight != null
            ? (
                width: post.photoWidth!.toDouble(),
                height: post.photoHeight!.toDouble()
              )
            : null,
      );
  final Future<LikeResult> Function(String postId, bool liked)? setLike;
  final CommentsLoader Function(String postId)? commentsForPost;
  final String Function(FitCheckComment comment)? commentAuthor;
  final ({double width, double height})? Function(FitCheckPost post)? photoSize;
}

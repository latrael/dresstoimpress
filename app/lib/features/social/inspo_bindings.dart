import '../../core/models.dart';
import 'comments_sheet.dart';

/// UI callbacks supplied by the shared client; this layer sends no HTTP requests.
class InspoBindings {
  const InspoBindings(
      {this.setLike, this.commentsForPost, this.commentAuthor, this.photoSize});
  final Future<LikeResult> Function(String postId, bool liked)? setLike;
  final CommentsLoader Function(String postId)? commentsForPost;
  final String Function(FitCheckComment comment)? commentAuthor;
  final ({double width, double height})? Function(FitCheckPost post)? photoSize;
}

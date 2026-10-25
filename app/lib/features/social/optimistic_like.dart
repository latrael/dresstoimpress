import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import '../../core/models.dart';

/// Serializes explicit state writes; never retries a toggle request.
class OptimisticLike extends ChangeNotifier {
  OptimisticLike({required bool liked, required int count, required this.write})
      : _confirmed = liked,
        _desired = liked,
        _count = count;
  final Future<LikeResult> Function(bool liked) write;
  bool _confirmed, _desired;
  int _count;
  int _version = 0;
  bool _pending = false, _running = false, _disposed = false;
  String? error;
  bool get liked => _desired;
  int get count =>
      math.max(0, _count + (_desired ? 1 : 0) - (_confirmed ? 1 : 0));
  bool get saving => _running || _pending;
  void acceptServer(bool liked, int count) {
    if (saving || _disposed) return;
    _confirmed = _desired = liked;
    _count = count;
  }

  void toggle() {
    if (_disposed) return;
    _desired = !_desired;
    _version++;
    _pending = true;
    error = null;
    notifyListeners();
    _drain();
  }

  Future<void> _drain() async {
    if (_running || _disposed) return;
    _running = true;
    while (_pending && !_disposed) {
      _pending = false;
      final target = _desired, version = _version;
      try {
        final result = await write(target);
        if (_disposed) return;
        if (result.liked != target) {
          throw StateError('Like state was not confirmed');
        }
        _confirmed = result.liked;
        _count = result.likeCount;
        // A later tap may have reversed the in-flight request.
        _pending = _desired != _confirmed;
      } catch (_) {
        if (_disposed) return;
        if (version == _version) {
          _desired = _confirmed;
          _pending = false;
          error = 'Could not update like. Please try again.';
        } else {
          // Only send the newer user intent; do not automatically retry the failure.
          _pending = true;
        }
      }
      notifyListeners();
    }
    _running = false;
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

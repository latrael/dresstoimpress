import '../../core/api.dart';
import '../../core/models.dart';
import 'reels_browse.dart';

/// The UI consumes the shared client; it owns no transport or generation policy.
class ReelsBindings {
  ReelsBindings(this.api);
  final Api api;
  static Map<String, ReelTryOn> states(Map<String, TryOnState> values) => {
        for (final entry in values.entries)
          entry.key: (
            status: entry.value.status,
            url: entry.value.imageUrl,
            mode: entry.value.mode
          )
      };
  Future<Map<String, ReelTryOn>> prepare(List<String> ids) async =>
      states(await api.prefetchTryOns(ids));
  Future<Map<String, ReelTryOn>> load(List<String> ids) async =>
      states(await api.tryOnStatus(ids));
}

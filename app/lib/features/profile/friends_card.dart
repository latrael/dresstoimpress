import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/niche_icons.dart';
import '../shared/niche_theme.dart';

/// Profile → Friends: my handle + friend code (Copy), one "Add friend" field (handle or code),
/// and the friends list with Remove. Friendship is mutual on add, no requests.
class FriendsCard extends StatefulWidget {
  const FriendsCard({super.key, required this.api, this.onChanged});
  final Api api;
  final VoidCallback? onChanged;
  @override
  State<FriendsCard> createState() => _FriendsCardState();
}

class _FriendsCardState extends State<FriendsCard> {
  final input = TextEditingController();
  FriendIdentity? me;
  List<Friend> friends = const [];
  String? note;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final id = await widget.api.myCode();
      final list = await widget.api.friends();
      if (!mounted) return;
      setState(() {
        me = id;
        friends = list;
      });
    } catch (_) {
      if (mounted) setState(() => note = 'Could not load friends.');
    }
  }

  Future<void> add() async {
    final q = input.text.trim();
    if (q.isEmpty || busy) return;
    setState(() {
      busy = true;
      note = null;
    });
    try {
      final list = await widget.api.addFriend(q);
      if (!mounted) return;
      input.clear();
      setState(() {
        friends = list;
        note = 'Added.';
      });
      HapticFeedback.lightImpact();
      widget.onChanged?.call();
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => note = e.status == 404
            ? 'No one with that handle or code.'
            : e.status == 422
                ? "That's you."
                : 'Could not add. Try again.');
      }
    } catch (_) {
      if (mounted) setState(() => note = 'Could not add. Try again.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> remove(Friend f) async {
    try {
      final list = await widget.api.removeFriend(f.id);
      if (mounted) setState(() => friends = list);
      widget.onChanged?.call();
    } catch (_) {
      if (mounted) setState(() => note = 'Could not remove. Try again.');
    }
  }

  Future<void> copy(String text) async {
    await Clipboard.setData(ClipboardData(text: text));
    if (mounted) setState(() => note = 'Copied $text');
  }

  @override
  Widget build(BuildContext context) {
    final t = Niche.of(context);
    final theme = Theme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text('Friends', style: theme.textTheme.titleLarge),
        if (friends.isNotEmpty) ...[
          const SizedBox(width: 8),
          Text('${friends.length}', style: Niche.ui(14, 20, FontWeight.w600, t.muted)),
        ],
      ]),
      const SizedBox(height: 8),
      if (me != null)
        Wrap(spacing: 8, runSpacing: 8, children: [
          _codeChip(context, '@${me!.handle}', () => copy('@${me!.handle}')),
          _codeChip(context, me!.friendCode, () => copy(me!.friendCode)),
        ]),
      const SizedBox(height: 10),
      Row(children: [
        Expanded(
            child: TextField(
                controller: input,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => add(),
                decoration: const InputDecoration(
                    hintText: 'Add friend · handle or code', isDense: true, prefixIcon: Icon(NicheIcons.add)))),
        const SizedBox(width: 8),
        FilledButton(onPressed: busy ? null : add, child: Text(busy ? '…' : 'Add')),
      ]),
      if (note != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(note!, style: Niche.ui(13, 18, FontWeight.w500, t.muted))),
      const SizedBox(height: 6),
      for (final f in friends)
        ListTile(
            key: ValueKey('friend-${f.id}'),
            contentPadding: EdgeInsets.zero,
            dense: true,
            leading: CircleAvatar(
                radius: 16,
                backgroundColor: t.blush,
                foregroundImage: f.photoUrl == null ? null : NetworkImage(widget.api.imageUrl(f.photoUrl!)),
                child: Text(f.displayName.isEmpty ? '?' : f.displayName[0].toUpperCase(),
                    style: Niche.ui(13, 16, FontWeight.w700, t.brand))),
            title: Text(f.displayName, style: Niche.ui(15, 20, FontWeight.w600, t.ink)),
            subtitle: Text('@${f.handle}', style: Niche.ui(13, 18, FontWeight.w500, t.muted)),
            trailing: TextButton(onPressed: () => remove(f), child: const Text('Remove'))),
      if (me != null && friends.isEmpty)
        Text('Share your code so friends can add you.', style: Niche.ui(13, 18, FontWeight.w500, t.muted)),
    ]);
  }

  Widget _codeChip(BuildContext context, String text, VoidCallback onCopy) {
    final t = Niche.of(context);
    return Material(
        color: t.blush,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: onCopy,
            child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 6, 10, 6),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text(text, style: Niche.ui(14, 20, FontWeight.w700, t.brand)),
                  const SizedBox(width: 6),
                  Icon(Icons.copy_rounded, size: 15, color: t.brand),
                ]))));
  }
}

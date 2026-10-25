import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';

typedef CommentsPageData = ({
  List<FitCheckComment> comments,
  int total,
  String? nextBefore
});
typedef CommentsLoader = Future<CommentsPageData> Function(String? before);

class CommentsSheet extends StatefulWidget {
  const CommentsSheet(
      {super.key,
      required this.api,
      required this.postId,
      required this.initial,
      required this.onAdded,
      this.loadPage,
      this.authorLabel,
      this.onTotal});
  final Api api;
  final String postId;
  final List<FitCheckComment> initial;
  final ValueChanged<FitCheckComment> onAdded;
  final CommentsLoader? loadPage;
  final String Function(FitCheckComment)? authorLabel;
  final ValueChanged<int>? onTotal;
  @override
  State<CommentsSheet> createState() => _CommentsSheetState();
}

class _CommentsSheetState extends State<CommentsSheet> {
  final text = TextEditingController();
  final scroll = ScrollController();
  late final comments = [...widget.initial]
    ..sort((a, b) => (a.createdAt ?? '').compareTo(b.createdAt ?? ''));
  bool sending = false, loading = false, loaded = false;
  String? nextBefore;
  String? loadError;
  String? error;
  late int knownTotal = widget.initial.length;
  @override
  void initState() {
    super.initState();
    if (widget.loadPage == null) {
      loaded = true;
      bottom();
    } else {
      load();
    }
  }

  void bottom() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && scroll.hasClients) {
          scroll.jumpTo(scroll.position.maxScrollExtent);
        }
      });
  @override
  void dispose() {
    text.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> load({bool older = false}) async {
    if (loading || widget.loadPage == null) return;
    if (older && nextBefore == null) return;
    setState(() {
      loading = true;
      loadError = null;
    });
    final oldOffset = scroll.hasClients ? scroll.offset : 0.0;
    final oldExtent = scroll.hasClients ? scroll.position.maxScrollExtent : 0.0;
    try {
      final page = await widget.loadPage!(older ? nextBefore : null);
      if (!mounted) return;
      // Preserve local sends and deduplicate preview/page overlaps by stable ID.
      final byId = <String, FitCheckComment>{
        for (final c in page.comments) c.id: c
      };
      for (final c in comments) {
        byId.putIfAbsent(c.id, () => c);
      }
      setState(() {
        comments.clear();
        comments.addAll(byId.values);
        comments
            .sort((a, b) => (a.createdAt ?? '').compareTo(b.createdAt ?? ''));
        nextBefore = page.nextBefore;
        loading = false;
        loaded = true;
      });
      knownTotal = page.total > knownTotal ? page.total : knownTotal;
      widget.onTotal?.call(knownTotal);
      if (older) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && scroll.hasClients) {
            scroll.jumpTo(
                (oldOffset + scroll.position.maxScrollExtent - oldExtent)
                    .clamp(0, scroll.position.maxScrollExtent));
          }
        });
      } else {
        bottom();
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          loading = false;
          loadError = 'Could not load comments. Retry';
        });
      }
    }
  }

  Future<void> send() async {
    final draft = text.text.trim();
    if (draft.isEmpty || draft.length > 280 || sending) return;
    setState(() {
      sending = true;
      error = null;
    });
    try {
      final added = await widget.api.commentFitCheck(widget.postId, draft);
      final isNew = !comments.any((c) => c.id == added.id);
      final reportedTotal = added.commentCount ?? knownTotal + (isNew ? 1 : 0);
      knownTotal = reportedTotal > knownTotal ? reportedTotal : knownTotal;
      widget.onAdded(added);
      if (!mounted) return;
      setState(() {
        if (!comments.any((c) => c.id == added.id)) comments.add(added);
        text.clear();
      });
      bottom();
    } catch (e) {
      if (mounted) setState(() => error = featureError(e));
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final keyboard = MediaQuery.viewInsetsOf(context).bottom;
    final height =
        (MediaQuery.sizeOf(context).height - keyboard - 40).clamp(180.0, 660.0);
    return Padding(
        padding: EdgeInsets.only(bottom: keyboard),
        child: SizedBox(
            height: height,
            child: SafeArea(
                top: false,
                child: Column(children: [
                  Row(children: [
                    const SizedBox(width: 16),
                    Text('Comments',
                        style: Theme.of(context).textTheme.titleLarge),
                    const Spacer(),
                    IconButton(
                        tooltip: 'Close comments',
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(NicheIcons.close))
                  ]),
                  const Divider(height: 1),
                  if (loadError != null)
                    TextButton(
                        onPressed: () => load(older: loaded),
                        child: Text(loadError!)),
                  if (!loaded && loading)
                    const Padding(
                        padding: EdgeInsets.all(20),
                        child: CircularProgressIndicator()),
                  if (loaded && nextBefore != null)
                    TextButton(
                        onPressed: loading ? null : () => load(older: true),
                        child:
                            Text(loading ? 'Loading…' : 'Load older comments')),
                  Expanded(
                      child: comments.isEmpty
                          ? const Center(child: Text('Start the conversation.'))
                          : ListView.builder(
                              controller: scroll,
                              padding: const EdgeInsets.all(16),
                              itemCount: comments.length,
                              itemBuilder: (context, i) => Padding(
                                  padding: const EdgeInsets.only(bottom: 16),
                                  child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                            widget.authorLabel
                                                    ?.call(comments[i]) ??
                                                comments[i].userId,
                                            style: Theme.of(context)
                                                .textTheme
                                                .titleMedium),
                                        Text(comments[i].text)
                                      ])))),
                  if (error != null)
                    Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Text(error!)),
                  Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 8, 12),
                      child: Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Expanded(
                                child: TextField(
                                    controller: text,
                                    enabled: !sending,
                                    minLines: 1,
                                    maxLines: 3,
                                    maxLength: 280,
                                    decoration: const InputDecoration(
                                        hintText: 'Add a comment…',
                                        counterText: '',
                                        isDense: true))),
                            IconButton(
                                tooltip: 'Send comment',
                                onPressed: sending ? null : send,
                                icon: sending
                                    ? const SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2))
                                    : const Icon(NicheIcons.sendOutlined))
                          ])),
                ]))));
  }
}

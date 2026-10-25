import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/feature_ui.dart';

class CommentsSheet extends StatefulWidget {
  const CommentsSheet(
      {super.key,
      required this.api,
      required this.postId,
      required this.initial,
      required this.onAdded});
  final Api api;
  final String postId;
  final List<FitCheckComment> initial;
  final ValueChanged<FitCheckComment> onAdded;
  @override
  State<CommentsSheet> createState() => _CommentsSheetState();
}

class _CommentsSheetState extends State<CommentsSheet> {
  final text = TextEditingController();
  final scroll = ScrollController();
  late final comments = [...widget.initial]
    ..sort((a, b) => (a.createdAt ?? '').compareTo(b.createdAt ?? ''));
  bool sending = false;
  String? error;
  @override
  void initState() {
    super.initState();
    bottom();
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

  Future<void> send() async {
    final draft = text.text.trim();
    if (draft.isEmpty || draft.length > 280 || sending) return;
    setState(() {
      sending = true;
      error = null;
    });
    try {
      final added = await widget.api.commentFitCheck(widget.postId, draft);
      widget.onAdded(added);
      if (!mounted) return;
      setState(() {
        comments.add(added);
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
                        icon: const Icon(Icons.close))
                  ]),
                  const Divider(height: 1),
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
                                        Text(comments[i].userId,
                                            style: const TextStyle(
                                                fontWeight: FontWeight.w600)),
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
                                    : const Icon(Icons.send_outlined))
                          ])),
                ]))));
  }
}

import 'niche_theme.dart';
import 'niche_icons.dart';
import 'package:flutter/material.dart';

class FeaturePage extends StatelessWidget {
  const FeaturePage(
      {super.key, required this.title, required this.child, this.actions});
  final String title;
  final Widget child;
  final List<Widget>? actions;
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(title),
            actions: actions,
            automaticallyImplyLeading: false,
            leading: Navigator.canPop(context)
                ? IconButton(
                    tooltip: 'Back',
                    icon: const Icon(NicheIcons.back),
                    onPressed: () => Navigator.maybePop(context))
                : null),
        body: Center(
            child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 540),
                child: child)),
      );
}

class AsyncContent<T> extends StatefulWidget {
  const AsyncContent({super.key, required this.load, required this.builder});
  final Future<T> Function() load;
  final Widget Function(T data) builder;
  @override
  State<AsyncContent<T>> createState() => _AsyncContentState<T>();
}

class _AsyncContentState<T> extends State<AsyncContent<T>> {
  late Future<T> future = widget.load();
  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
              child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Text(
                        'Could not load this. Check your connection and try again.'),
                    TextButton(
                        onPressed: () => setState(() => future = widget.load()),
                        child: const Text('Retry')),
                  ])));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        return widget.builder(snapshot.data as T);
      });
}

class PiecePhoto extends StatelessWidget {
  const PiecePhoto({super.key, required this.url, required this.label});
  final String url;
  final String label;
  @override
  Widget build(BuildContext context) => ColoredBox(
      color: Niche.of(context).stone,
      child: url.isEmpty
          ? const Center(child: Icon(NicheIcons.imageOutlined))
          : Image.network(url,
              fit: BoxFit.contain,
              semanticLabel: label,
              webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
              errorBuilder: (_, error, stack) =>
                  const Center(child: Text('Photo unavailable'))));
}

String featureError(Object e) => e.toString().replaceFirst('Exception: ', '');

class ScoreCard extends StatelessWidget {
  const ScoreCard(
      {super.key,
      required this.score,
      required this.verdict,
      required this.notes,
      required this.breakdown});
  final int score;
  final String verdict;
  final List<String> notes;
  final Map<String, String> breakdown;
  @override
  Widget build(BuildContext context) => Card(
      child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Fit Score · $score/100',
                style: Theme.of(context).textTheme.titleLarge),
            Text(verdict),
            const SizedBox(height: 8),
            for (final note in notes) Text(note),
            const SizedBox(height: 12),
            for (final entry in breakdown.entries)
              Text('${entry.key} · ${entry.value}'),
          ])));
}

import '../shared/niche_theme.dart';
import '../shared/niche_photo.dart';
import '../shared/natural_photo_frame.dart';
import '../shared/niche_icons.dart';
import 'package:flutter/material.dart';
import '../fits/fits_screen.dart';
import '../../core/models.dart';
import '../store/store_controller.dart';
import '../store/cart_screen.dart';
import '../shared/feature_ui.dart';
import '../shared/pick_photo.dart';
import '../closet/closet_screen.dart';

class ProductGrid extends StatelessWidget {
  const ProductGrid(
      {super.key,
      required this.products,
      required this.store,
      required this.onOpen});
  final List<RankedProduct> products;
  final StoreController store;
  final void Function(RankedProduct) onOpen;
  @override
  Widget build(BuildContext context) => Column(children: [
        for (final card in products)
          Padding(
              padding: const EdgeInsets.only(bottom: 28),
              child: NichePress(
                  child: InkWell(
                      key: ValueKey('suggested-${card.id}'),
                      borderRadius: BorderRadius.circular(28),
                      onTap: () => onOpen(card),
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            ClipRRect(
                                borderRadius: BorderRadius.circular(28),
                                child: NaturalPhotoFrame(
                                    url: store.imageUrl(card.product.imageUrl),
                                    child: NichePhoto(
                                        url: store
                                            .imageUrl(card.product.imageUrl),
                                        label: card.product.name))),
                            const SizedBox(height: 12),
                            Text(
                                retailerName(card.product.retailer)
                                    .toUpperCase(),
                                style: Theme.of(context)
                                    .textTheme
                                    .labelSmall!
                                    .copyWith(color: Niche.wine)),
                            const SizedBox(height: 5),
                            Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Expanded(
                                      child: Text(card.product.name,
                                          style: Theme.of(context)
                                              .textTheme
                                              .headlineSmall)),
                                  const SizedBox(width: 12),
                                  Text(dollars(card.product.effectivePrice),
                                      style: Niche.price)
                                ])
                          ]))))
      ]);
}

class LikedScreen extends StatefulWidget {
  const LikedScreen({super.key, required this.store, required this.onOpen});
  final StoreController store;
  final void Function(RankedProduct) onOpen;
  @override
  State<LikedScreen> createState() => _LikedScreenState();
}

class _LikedScreenState extends State<LikedScreen> {
  late Future<List<RankedProduct>> products = load();
  Future<List<RankedProduct>> load() async => widget.store.demo
      ? widget.store.feed
          .where((p) => widget.store.saved.contains(p.id))
          .toList()
      : (await widget.store.api.wishlist())
          .map((p) => RankedProduct(product: p))
          .toList();
  @override
  Widget build(BuildContext context) => FeaturePage(
      title: 'Liked',
      child: FutureBuilder<List<RankedProduct>>(
          future: products,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                  child: TextButton(
                      onPressed: () => setState(() {
                            products = load();
                          }),
                      child: const Text('Could not load liked pieces. Retry')));
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.data!.isEmpty) {
              return const Center(child: Text('Like a piece to find it here.'));
            }
            return ListView(padding: const EdgeInsets.all(20), children: [
              ProductGrid(
                  products: snapshot.data!,
                  store: widget.store,
                  onOpen: widget.onOpen)
            ]);
          }));
}

class DiscoverScreen extends StatefulWidget {
  const DiscoverScreen(
      {super.key,
      required this.store,
      required this.onOpen,
      this.initialQuery,
      this.picker});
  final String? initialQuery;
  final PhotoPicker? picker;
  final StoreController store;
  final void Function(RankedProduct) onOpen;
  @override
  State<DiscoverScreen> createState() => _DiscoverScreenState();
}

class _DiscoverScreenState extends State<DiscoverScreen> {
  final text = TextEditingController();
  List<RankedProduct> similar = [], goesWith = [];
  List<ClosetItem> owned = [];
  late Future<StyleChips> idle = loadIdle();
  bool loading = false;
  String? error;
  String query = '';
  PickedPhoto? photo;
  int generation = 0;
  Future<StyleChips> loadIdle() async {
    if (!widget.store.demo) return widget.store.api.searchStyles();
    final counts = <String, int>{};
    for (final p in widget.store.feed) {
      for (final tag in p.product.styleTags) {
        counts[tag] = (counts[tag] ?? 0) + 1;
      }
    }
    return StyleChips(
        styles: [
          for (final e in counts.entries) StyleTag(tag: e.key, count: e.value)
        ],
        trending: widget.store.feed
            .take(8)
            .map((p) => TrendingProduct(product: p.product))
            .toList());
  }

  @override
  void initState() {
    super.initState();
    if (widget.initialQuery?.isNotEmpty == true) {
      text.text = widget.initialQuery!;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) search(text.text);
      });
    }
  }

  @override
  void didUpdateWidget(covariant DiscoverScreen old) {
    super.didUpdateWidget(old);
    if (widget.initialQuery != old.initialQuery &&
        widget.initialQuery != null) {
      text.text = widget.initialQuery!;
      search(text.text);
    }
  }

  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  void apply(_DiscoverViewResult result, int request) {
    if (mounted && request == generation) {
      setState(() {
        similar = result.similar;
        goesWith = result.catalogPairs;
        owned = result.ownedPairs;
        loading = false;
      });
    }
  }

  Future<void> search(String value) async {
    FocusManager.instance.primaryFocus?.unfocus();
    final request = ++generation;
    setState(() {
      query = value.trim();
      loading = query.isNotEmpty;
      error = null;
      photo = null;
    });
    if (query.isEmpty) return;
    try {
      if (widget.store.demo) {
        apply(
            _DiscoverViewResult(
                similar: widget.store.feed
                    .where((p) =>
                        '${p.product.name} ${p.product.styleTags.join(' ')} ${p.product.category}'
                            .toLowerCase()
                            .contains(query.toLowerCase()))
                    .toList()),
            request);
        return;
      }
      var result =
          _DiscoverViewResult.fromText(await widget.store.api.search(query));
      if (result.similar.isEmpty) {
        final filters = await widget.store.api.vibe(query);
        final queries = {
          ...filters.keywords,
          ...filters.styles,
          ...filters.categories
        }.take(3);
        if (queries.isNotEmpty) {
          final parts = await Future.wait(queries.map((q) async =>
              _DiscoverViewResult.fromText(await widget.store.api.search(q))));
          final matches = <String, RankedProduct>{};
          final pairs = <String, RankedProduct>{};
          final closet = <String, ClosetItem>{};
          for (final p in parts) {
            for (final card in p.similar) {
              matches[card.id] = card;
            }
            for (final card in p.catalogPairs) {
              pairs[card.id] = card;
            }
            for (final item in p.ownedPairs) {
              closet[item.id] = item;
            }
          }
          result = _DiscoverViewResult(
              similar: matches.values.toList(),
              catalogPairs: pairs.values.toList(),
              ownedPairs: closet.values.toList());
        }
      }
      apply(result, request);
    } catch (_) {
      if (mounted && request == generation) {
        setState(() {
          loading = false;
          error = 'Could not search. Check your connection and retry.';
        });
      }
    }
  }

  Future<void> photoSearch() async {
    try {
      final selected = await (widget.picker != null
          ? widget.picker!()
          : choosePhoto(context));
      if (selected == null || !mounted) return;
      final request = ++generation;
      setState(() {
        photo = selected;
        query = 'Photo search';
        loading = true;
        error = null;
      });
      if (widget.store.demo) {
        setState(() {
          loading = false;
          error = 'Connect to search a photo privately.';
        });
        return;
      }
      final result = _DiscoverViewResult.fromPhoto(await widget.store.api
          .searchPhoto(selected.bytes, mimeType: selected.mimeType));
      apply(result, request);
    } catch (_) {
      if (mounted) {
        setState(() {
          loading = false;
          error = 'Photo search is unavailable right now. Try again.';
        });
      }
    }
  }

  List<RankedProduct> mix(List<TrendingProduct> trending) {
    final out = <String, RankedProduct>{};
    for (var i = 0; i < 8; i++) {
      if (i < trending.length) {
        out[trending[i].id] = RankedProduct(product: trending[i].product);
      }
      if (i < widget.store.feed.length) {
        out[widget.store.feed[i].id] = widget.store.feed[i];
      }
    }
    return out.values.take(8).toList();
  }

  @override
  Widget build(BuildContext context) => ListView(
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: EdgeInsets.fromLTRB(16, 20, 16, Niche.bottomSpace(context)),
          children: [
            Text('Discover', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            NicheGlass(
                radius: 999,
                child: TextField(
                    controller: text,
                    onTapOutside: (_) =>
                        FocusManager.instance.primaryFocus?.unfocus(),
                    textInputAction: TextInputAction.search,
                    onSubmitted: search,
                    decoration: InputDecoration(
                        hintText: 'Search a look…',
                        prefixIcon: IconButton(
                            tooltip: 'Search with a photo',
                            icon: const Icon(NicheIcons.cameraAltOutlined),
                            onPressed: loading ? null : photoSearch),
                        suffixIcon: IconButton(
                            tooltip: 'Search catalog',
                            icon: const Icon(NicheIcons.arrowForward),
                            onPressed: () => search(text.text))))),
            if (photo != null)
              Padding(
                  padding: const EdgeInsets.only(top: 16),
                  child: SizedBox(
                      height: 140,
                      child: Image.memory(photo!.bytes, fit: BoxFit.contain))),
            if (query.isNotEmpty)
              Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                      onPressed: () {
                        text.clear();
                        search('');
                      },
                      child: const Text('Clear search'))),
            const SizedBox(height: 20),
            if (query.isEmpty)
              Card(
                  child: ListTile(
                      leading: const Icon(NicheIcons.autoAwesome),
                      title: const Text('Fits for you'),
                      subtitle: const Text(
                          'Create outfits from your closet and new pieces'),
                      trailing: const Icon(NicheIcons.chevronRight),
                      onTap: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                              builder: (_) => FitsScreen(
                                  store: widget.store,
                                  onProduct: widget.onOpen))))),
            if (query.isEmpty && !loading)
              FutureBuilder<StyleChips>(
                  future: idle,
                  builder: (context, snapshot) {
                    if (snapshot.hasError) {
                      return TextButton(
                          onPressed: () => setState(() {
                                idle = loadIdle();
                              }),
                          child: const Text(
                              'Could not load styles and trending. Retry'));
                    }
                    if (!snapshot.hasData) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Explore a style'),
                          const SizedBox(height: 12),
                          Wrap(spacing: 8, runSpacing: 6, children: [
                            for (final tag in snapshot.data!.styles)
                              ActionChip(
                                  label: Text(tag.tag),
                                  onPressed: () {
                                    text.text = tag.tag;
                                    search(tag.tag);
                                  })
                          ]),
                          const SizedBox(height: 24),
                          Text(
                              widget.store.demo
                                  ? 'For you'
                                  : 'Trending + for you',
                              style: Theme.of(context).textTheme.titleLarge),
                          const SizedBox(height: 12),
                          ProductGrid(
                              products: mix(snapshot.data!.trending),
                              store: widget.store,
                              onOpen: widget.onOpen)
                        ]);
                  })
            else if (loading)
              const Center(child: CircularProgressIndicator())
            else if (error != null)
              TextButton(
                  onPressed: () =>
                      photo != null ? photoSearch() : search(query),
                  child: Text(error!))
            else ...[
              Text('Similar items',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              if (similar.isEmpty)
                const Text('No matches yet. Try another look.')
              else
                ProductGrid(
                    products: similar,
                    store: widget.store,
                    onOpen: widget.onOpen),
              const SizedBox(height: 24),
              Text('Goes with it',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              for (final item in owned)
                ListTile(
                    leading: const Icon(NicheIcons.checkroomOutlined),
                    title: Text(item.label ?? item.category),
                    subtitle: const Text('Already in your closet'),
                    onTap: () => Navigator.push<void>(
                        context,
                        MaterialPageRoute(
                            builder: (_) =>
                                ClosetScreen(api: widget.store.api)))),
              if (goesWith.isEmpty && owned.isEmpty)
                const Text('No matching pieces to show yet.')
              else
                ProductGrid(
                    products: goesWith,
                    store: widget.store,
                    onOpen: widget.onOpen),
            ],
          ]);
}

class _DiscoverViewResult {
  const _DiscoverViewResult(
      {this.similar = const [],
      this.catalogPairs = const [],
      this.ownedPairs = const []});
  final List<RankedProduct> similar, catalogPairs;
  final List<ClosetItem> ownedPairs;
  factory _DiscoverViewResult.fromText(SearchResult r) => _DiscoverViewResult(
          similar: r.similar.map((p) => RankedProduct(product: p)).toList(),
          catalogPairs: [
            for (final p in r.goesWith)
              if (p.product != null)
                RankedProduct(product: p.product!, reason: p.reason)
          ],
          ownedPairs: [
            for (final p in r.goesWith)
              if (p.closetItem != null) p.closetItem!
          ]);
  factory _DiscoverViewResult.fromPhoto(PhotoSearchResult r) =>
      _DiscoverViewResult(similar: r.similar, catalogPairs: [
        for (final p in r.goesWith)
          if (p.product != null)
            RankedProduct(product: p.product!, reason: p.reason)
      ], ownedPairs: [
        for (final p in r.goesWith)
          if (p.closetItem != null) p.closetItem!
      ]);
}

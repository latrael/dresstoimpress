import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';

import 'core/api.dart';
import 'core/config.dart';
import 'core/models.dart';
import 'features/feed/quick_browse.dart';
import 'features/social/social_feed.dart';
import 'features/search/catalog_search.dart';
import 'features/profile/profile_screen.dart';
import 'features/product/size_advice_sheet.dart';
import 'features/product/try_on.dart';
import 'features/product/complete_look_screen.dart';
import 'features/store/cart_screen.dart';
import 'features/store/store_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Config.load();
  runApp(NicheApp(
      store: StoreController(
          api: Api.instance, demo: Config.current.apiKey.isEmpty)));
}

class NicheApp extends StatelessWidget {
  const NicheApp({super.key, required this.store});
  final StoreController store;
  @override
  Widget build(BuildContext context) => MaterialApp(
      scrollBehavior: const MaterialScrollBehavior().copyWith(dragDevices: {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.trackpad,
        PointerDeviceKind.stylus,
      }),
      title: 'Niche',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFFFFFBF0),
          colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF722F42),
              surface: const Color(0xFFFFFBF0)),
          appBarTheme: const AppBarTheme(
              backgroundColor: Color(0xFFFFFBF0), centerTitle: false),
          inputDecorationTheme: InputDecorationTheme(
              border:
                  OutlineInputBorder(borderRadius: BorderRadius.circular(24))),
          filledButtonTheme: FilledButtonThemeData(
              style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF722F42),
                  foregroundColor: Colors.white))),
      home: ShopShell(store: store));
}

class ShopShell extends StatefulWidget {
  const ShopShell({super.key, required this.store});
  final StoreController store;
  @override
  State<ShopShell> createState() => _ShopShellState();
}

class _ShopShellState extends State<ShopShell> {
  int tab = 0;
  int anchor = 0;
  bool savedOnly = false;
  String query = '';
  late final catalog = CatalogSearch(store.api);
  final search = TextEditingController();
  StoreController get store => widget.store;
  @override
  void initState() {
    super.initState();
    store.load();
  }

  @override
  void dispose() {
    catalog.dispose();
    search.dispose();
    super.dispose();
  }

  List<RankedProduct> get visible {
    final words = query
        .toLowerCase()
        .trim()
        .split(RegExp(r'\s+'))
        .where((s) => s.isNotEmpty);
    final source = query.isNotEmpty && !store.demo ? catalog.cards : store.feed;
    return source.where((card) {
      final p = card.product;
      final text =
          '${p.name} ${p.brand} ${p.label} ${p.category} ${p.colors.join(' ')} ${p.styleTags.join(' ')}'
              .toLowerCase();
      return (!savedOnly || store.saved.contains(p.id)) &&
          (!store.demo && query.isNotEmpty || words.every(text.contains));
    }).toList();
  }

  void submitSearch(String value) {
    setState(() {
      query = value.trim();
      anchor = 0;
      tab = 1;
      savedOnly = false;
    });
    if (query.isNotEmpty && !store.demo) catalog.search(query);
  }

  void browse(int index) => setState(() {
        anchor = index;
        tab = 1;
      });
  void openProducts(List<RankedProduct> products) {
    Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => AnimatedBuilder(
                  animation: store,
                  builder: (context, _) => Scaffold(
                    appBar: AppBar(title: const Text('Quick Browse')),
                    body: Center(
                        child: ConstrainedBox(
                            constraints: const BoxConstraints(maxWidth: 540),
                            child: QuickBrowse(
                              products: products.map(browseMap).toList(),
                              savedIds: store.saved,
                              onSave: store.save,
                              onAddToCart: store.add,
                              imageUrl: store.imageUrl,
                              onSizeAdvice: store.demo
                                  ? null
                                  : (id) =>
                                      showSizeAdvice(context, store.api, id),
                              onTryOn: store.demo
                                  ? null
                                  : (id) =>
                                      requestTryOn(context, store.api, id),
                              onCompleteLook: store.demo ? null : completeLook,
                            ))),
                  ),
                )));
  }

  void completeLook(String id) => Navigator.push<void>(
      context,
      MaterialPageRoute(
          builder: (_) => CompleteLookScreen(
                api: store.api,
                productId: id,
                onProduct: (p) => openProducts([RankedProduct(product: p)]),
              )));

  Future<void> settings() async {
    await Navigator.push<void>(context,
        MaterialPageRoute(builder: (_) => ConnectionScreen(store: store)));
    if (mounted) {
      setState(() {
        anchor = 0;
        query = '';
        search.clear();
      });
    }
  }

  Widget content(
      List<RankedProduct> cards, List<RankedProduct> ordered, int start) {
    if (tab == 2) {
      return SocialFeed(
          key: ValueKey('${store.demo}:${store.api.settings.userId}'),
          store: store,
          onShop: openProducts);
    }
    if (store.loading ||
        query.isNotEmpty &&
            !store.demo &&
            catalog.loading &&
            catalog.cards.isEmpty) {
      return const Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
        CircularProgressIndicator(),
        SizedBox(height: 16),
        Text('Finding pieces for you…')
      ]));
    }
    if (query.isNotEmpty &&
        !store.demo &&
        catalog.error != null &&
        catalog.cards.isEmpty) {
      return Center(
          child: TextButton(
              onPressed: () => catalog.search(query),
              child: Text(catalog.error!)));
    }
    if (store.error != null) {
      return Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
        Padding(padding: const EdgeInsets.all(24), child: Text(store.error!)),
        FilledButton(onPressed: store.load, child: const Text('Try again'))
      ]));
    }
    if (tab == 1) {
      return QuickBrowse(
        key: ValueKey(
            '${store.api.settings.userId}:${store.demo}:$query:$savedOnly:$start'),
        products: ordered.map(browseMap).toList(),
        savedIds: store.saved,
        onSave: store.save,
        onAddToCart: store.add,
        imageUrl: store.imageUrl,
        onSizeAdvice:
            store.demo ? null : (id) => showSizeAdvice(context, store.api, id),
        onTryOn:
            store.demo ? null : (id) => requestTryOn(context, store.api, id),
        onCompleteLook: store.demo ? null : completeLook,
      );
    }
    if (cards.isEmpty) {
      return Center(
          child: Text(savedOnly
              ? 'Double-tap a piece to save it here.'
              : 'No matches. Try a different search.'));
    }
    return CustomScrollView(slivers: [
      SliverToBoxAdapter(
          child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(savedOnly ? 'Your saved pieces' : 'Suggested for you',
                        style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 6),
                    const Text('Find something that feels like you.'),
                  ]))),
      SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          sliver: SliverGrid(
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: 14,
                mainAxisSpacing: 16,
                childAspectRatio: .67),
            delegate: SliverChildBuilderDelegate((context, i) {
              final p = cards[i].product;
              return InkWell(
                  key: ValueKey('suggested-${p.id}'),
                  borderRadius: BorderRadius.circular(14),
                  onTap: () => browse(i),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                            child: SizedBox(
                                width: double.infinity,
                                child: ClipRRect(
                                    borderRadius: BorderRadius.circular(14),
                                    child: ProductPhoto(
                                        url: store.imageUrl(p.imageUrl),
                                        name: p.name)))),
                        const SizedBox(height: 8),
                        Text(p.name,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        Text(
                            '${retailerName(p.retailer)} · ${dollars(p.effectivePrice)}'),
                      ]));
            }, childCount: cards.length),
          )),
      const SliverToBoxAdapter(child: SizedBox(height: 24)),
    ]);
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: Listenable.merge([store, catalog]),
      builder: (context, _) {
        final cards = visible;
        final start = anchor < cards.length ? anchor : 0;
        final ordered = [...cards.skip(start), ...cards.take(start)];
        return Scaffold(
          appBar: AppBar(
              title: Text(
                  tab == 0
                      ? 'Niche'
                      : tab == 1
                          ? 'Quick Browse'
                          : 'Fit Check',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              actions: [
                IconButton(
                    tooltip: savedOnly ? 'Show all pieces' : 'Saved pieces',
                    onPressed: () => setState(() {
                          savedOnly = !savedOnly;
                          anchor = 0;
                          tab = 0;
                        }),
                    icon: Icon(
                        savedOnly ? Icons.favorite : Icons.favorite_border)),
                if (!store.demo)
                  IconButton(
                      tooltip: 'Your profile',
                      icon: const Icon(Icons.person_outline),
                      onPressed: () => Navigator.push<void>(
                          context,
                          MaterialPageRoute(
                              builder: (_) => ProfileScreen(
                                  api: store.api, onChanged: store.load)))),
                IconButton(
                    tooltip: 'Settings',
                    onPressed: settings,
                    icon: const Icon(Icons.tune)),
                Padding(
                    padding: const EdgeInsets.only(right: 12),
                    child: Badge(
                        label: Text('${store.cart.count}'),
                        isLabelVisible: store.cart.count > 0,
                        child: IconButton(
                            tooltip: 'Your cart',
                            onPressed: () => Navigator.push<void>(
                                context,
                                MaterialPageRoute(
                                    builder: (_) => CartScreen(store: store))),
                            icon: const Icon(Icons.shopping_bag_outlined)))),
              ]),
          body: Column(children: [
            if (store.demo)
              Material(
                  color: const Color(0xFFF0E5E5),
                  child: ListTile(
                      dense: true,
                      title: const Text(
                          'Demo mode · sample catalog and local cart'),
                      trailing: TextButton(
                          onPressed: settings, child: const Text('Connect')))),
            if (store.accountWarning != null)
              ListTile(
                  title: Text(store.accountWarning!),
                  trailing: TextButton(
                      onPressed: store.load, child: const Text('Retry'))),
            Expanded(
                child: Center(
                    child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 540),
                        child: content(cards, ordered, start)))),
            if (tab != 2 && query.isNotEmpty && !store.demo) ...[
              if (catalog.error != null && catalog.cards.isNotEmpty)
                Text(catalog.error!),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Text('${catalog.cards.length} of ${catalog.total} matches'),
                if (catalog.nextOffset != null)
                  TextButton(
                      onPressed: catalog.loading ? null : catalog.more,
                      child: Text(catalog.loading ? 'Loading…' : 'Load more')),
                TextButton(
                    onPressed: () {
                      search.clear();
                      submitSearch('');
                    },
                    child: const Text('Clear')),
              ]),
            ],
            if (tab != 2)
              Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 8),
                  child: Center(
                      child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 500),
                          child: TextField(
                            controller: search,
                            textInputAction: TextInputAction.search,
                            decoration: InputDecoration(
                                hintText: 'Search a look…',
                                prefixIcon: const Icon(Icons.search),
                                suffixIcon: IconButton(
                                    tooltip: 'Search catalog',
                                    icon: const Icon(Icons.arrow_upward),
                                    onPressed: () =>
                                        submitSearch(search.text))),
                            onSubmitted: submitSearch,
                          )))),
          ]),
          bottomNavigationBar: NavigationBar(
              selectedIndex: tab,
              onDestinationSelected: (value) => setState(() {
                    tab = value;
                    if (value == 0) {
                      query = '';
                      search.clear();
                      anchor = 0;
                    }
                  }),
              destinations: const [
                NavigationDestination(
                    icon: Icon(Icons.home_outlined), label: 'Home'),
                NavigationDestination(
                    icon: Icon(Icons.explore_outlined), label: 'Discover'),
                NavigationDestination(
                    icon: Icon(Icons.people_outline), label: 'Social'),
              ]),
        );
      });
}

class ProductPhoto extends StatelessWidget {
  const ProductPhoto({super.key, required this.url, required this.name});
  final String url;
  final String name;
  @override
  Widget build(BuildContext context) => ColoredBox(
      color: const Color(0xFFEDEAE4),
      child: url.isEmpty
          ? const Center(child: Icon(Icons.image_outlined))
          : Image.network(url,
              fit: BoxFit.contain,
              webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
              semanticLabel: name,
              errorBuilder: (_, error, stack) => const Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(Icons.image_outlined),
                    SizedBox(height: 8),
                    Text('Photo unavailable')
                  ]))));
}

class ConnectionScreen extends StatefulWidget {
  const ConnectionScreen({super.key, required this.store});
  final StoreController store;
  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  late final base = TextEditingController(text: Config.current.baseUrl);
  late final keyField = TextEditingController(text: Config.current.apiKey);
  late final user = TextEditingController(text: Config.current.userId);
  String status = '';
  bool busy = false;
  @override
  void dispose() {
    base.dispose();
    keyField.dispose();
    user.dispose();
    super.dispose();
  }

  Future<void> connect() async {
    final uri = Uri.tryParse(base.text.trim());
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        user.text.trim().isEmpty) {
      setState(() => status = 'Enter a valid server URL and user ID.');
      return;
    }
    setState(() {
      busy = true;
      status = 'Testing connection…';
    });
    try {
      await Config.save(Config.current.copyWith(
          baseUrl: base.text.trim(),
          apiKey: keyField.text.trim(),
          userId: user.text.trim()));
      if (!await widget.store.api.health()) {
        throw Exception('Server is not ready');
      }
      await widget.store.useMode(false);
      if (mounted) {
        setState(() => status = widget.store.error == null
            ? 'Connected. Your feed is ready.'
            : 'Server reached, but the feed failed. Check your key.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => status =
            'Could not connect. Check the server URL and key with Adam.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('Your connection')),
      body: Center(
          child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: ListView(padding: const EdgeInsets.all(24), children: [
                Text('Make it yours',
                    style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 12),
                const Text(
                    'Use the private connection details Adam shared with you. They stay on this device.'),
                const SizedBox(height: 24),
                TextField(
                    controller: base,
                    autocorrect: false,
                    keyboardType: TextInputType.url,
                    decoration: const InputDecoration(labelText: 'Server URL')),
                const SizedBox(height: 16),
                TextField(
                    controller: keyField,
                    obscureText: true,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration:
                        const InputDecoration(labelText: 'Shared access key')),
                const SizedBox(height: 16),
                TextField(
                    controller: user,
                    autocorrect: false,
                    decoration: const InputDecoration(labelText: 'User ID')),
                const SizedBox(height: 24),
                FilledButton(
                    onPressed: busy ? null : connect,
                    child: Text(busy ? 'Connecting…' : 'Test and connect')),
                const SizedBox(height: 12),
                Text(status),
                TextButton(
                    onPressed: busy
                        ? null
                        : () async {
                            await widget.store.useMode(true);
                            if (context.mounted) Navigator.pop(context);
                          },
                    child: const Text('Use demo mode')),
              ]))));
}

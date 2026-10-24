import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'features/profile/shopper_profile.dart';
import 'features/profile/body_photo_card.dart';

import 'core/api.dart';
import 'core/config.dart';
import 'core/models.dart';
import 'features/feed/quick_browse.dart';
import 'features/social/social_feed.dart';
import 'features/discover/discover_screen.dart';
import 'features/closet/closet_screen.dart';
import 'features/shared/feature_ui.dart';
import 'features/profile/profile_screen.dart';
import 'features/profile/onboarding_screen.dart';
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

class NicheApp extends StatefulWidget {
  const NicheApp({super.key, required this.store});
  final StoreController store;
  @override
  State<NicheApp> createState() => _NicheAppState();
}

class _NicheAppState extends State<NicheApp> {
  final navigation = GlobalKey<NavigatorState>();
  final shell = GlobalKey<_ShopShellState>();
  final entry = GlobalKey<_FirstVisitState>();
  StoreController get store => widget.store;
  void open(Widget page) => navigation.currentState
      ?.push(MaterialPageRoute<void>(builder: (_) => page));
  void seed(RankedProduct product) {
    navigation.currentState?.popUntil((r) => r.isFirst);
    shell.currentState?.openProducts([product]);
  }

  void settings() {
    navigation.currentState
        ?.push(MaterialPageRoute<void>(
            builder: (_) => ConnectionScreen(store: store)))
        .whenComplete(() {
      entry.currentState?.reload();
    });
  }

  void user() => open(FeaturePage(
      title: 'You',
      child: ListView(padding: const EdgeInsets.all(20), children: [
        for (final section in [
          ('Your style', 1),
          ('Stores you like', 2),
          ('Body scan', 3),
          ('Measurements & size', 4),
          ('Price preferences', 5)
        ])
          ListTile(
              title: Text(section.$1),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => open(OnboardingScreen(
                  api: store.api,
                  demo: store.demo,
                  initialStep: section.$2,
                  onSaved: () async {
                    await store.loadProfile(fromServer: !store.demo);
                    await store.load();
                  }))),
        if (!store.demo)
          ListTile(
              title: const Text('Style DNA'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => open(ProfileScreen(
                  api: store.api,
                  onChanged: () async {
                    await store.loadProfile(fromServer: !store.demo);
                    await store.load();
                  }))),
        ListTile(
            title: const Text('Orders'),
            leading: const Icon(Icons.receipt_long_outlined),
            onTap:
                store.demo ? null : () => open(OrderHistory(api: store.api))),
        ListTile(
            title: const Text('Connection settings'),
            leading: const Icon(Icons.tune),
            onTap: settings),
        if (!store.demo)
          ListTile(
              title: const Text('Private scan & try-on photo'),
              leading: const Icon(Icons.lock_outline),
              onTap: () => open(BodyPhotoCard(api: store.api))),
        ListTile(
            title: const Text('Log out on this device'),
            leading: const Icon(Icons.logout),
            onTap: () async {
              final p = await SharedPreferences.getInstance();
              await p.remove('niche.activeUser');
              await p.setBool('niche.signedOut', true);
              navigation.currentState?.popUntil((r) => r.isFirst);
              entry.currentState?.logOut();
            }),
        ListTile(
            title: const Text('Restart setup'),
            onTap: () async {
              final yes = await showDialog<bool>(
                  context: navigation.currentContext!,
                  builder: (context) => AlertDialog(
                          title: const Text('Restart setup?'),
                          content: const Text(
                              'Review your onboarding answers again. Your measurements and account are kept.'),
                          actions: [
                            TextButton(
                                onPressed: () => Navigator.pop(context, false),
                                child: const Text('Cancel')),
                            FilledButton(
                                onPressed: () => Navigator.pop(context, true),
                                child: const Text('Restart'))
                          ]));
              if (yes != true) return;
              await store.profile
                  .withCompletion(false)
                  .save(store.api.settings.userId);
              await store.loadProfile();
              navigation.currentState?.popUntil((r) => r.isFirst);
              entry.currentState?.restart();
            }),
      ])));
  @override
  Widget build(BuildContext context) => MaterialApp(
      navigatorKey: navigation,
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
      builder: (context, child) => Overlay.wrap(
          child: SafeArea(
              bottom: false,
              child: Stack(children: [
                Positioned.fill(
                    top: 56, child: child ?? const SizedBox.shrink()),
                Positioned(
                    top: 0,
                    left: 0,
                    right: 0,
                    child: Material(
                        color: const Color(0xFFFFFBF0),
                        child: SizedBox(
                            height: 56,
                            child: Row(children: [
                              const Padding(
                                  padding: EdgeInsets.only(left: 16),
                                  child: Text('Niche',
                                      style: TextStyle(
                                          fontSize: 22,
                                          fontWeight: FontWeight.w700))),
                              const Spacer(),
                              IconButton(
                                  tooltip: 'Liked',
                                  icon: const Icon(Icons.favorite_border),
                                  onPressed: () => open(
                                      LikedScreen(store: store, onOpen: seed))),
                              AnimatedBuilder(
                                  animation: store,
                                  builder: (context, _) => Badge(
                                      label: Text('${store.cart.count}'),
                                      isLabelVisible: store.cart.count > 0,
                                      child: IconButton(
                                          tooltip: 'Your cart',
                                          icon: const Icon(
                                              Icons.shopping_bag_outlined),
                                          onPressed: () =>
                                              open(CartScreen(store: store))))),
                              IconButton(
                                  tooltip: 'Closet',
                                  icon: const Icon(Icons.checkroom_outlined),
                                  onPressed: () => open(store.demo
                                      ? const FeaturePage(
                                          title: 'Closet',
                                          child: Center(
                                              child: Text(
                                                  'Connect your account to digitize your closet.')))
                                      : ClosetScreen(api: store.api))),
                              IconButton(
                                  tooltip: 'User',
                                  icon: const Icon(Icons.person_outline),
                                  onPressed: user),
                              const SizedBox(width: 8),
                            ])))),
              ]))),
      home: FirstVisit(key: entry, store: store, shellKey: shell));
}

class FirstVisit extends StatefulWidget {
  const FirstVisit({super.key, required this.store, this.shellKey});
  final GlobalKey? shellKey;
  final StoreController store;
  @override
  State<FirstVisit> createState() => _FirstVisitState();
}

class _FirstVisitState extends State<FirstVisit> {
  late Future<void> ready = load();
  bool active = false;
  bool hasReturning = false;
  void reload() {
    final next = load();
    setState(() {
      ready = next;
    });
  }

  void logOut() => setState(() => active = false);
  void restart() => setState(() => active = true);
  bool busy = false;
  String? error;
  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    try {
      await widget.store.loadProfile(fromServer: !widget.store.demo);
    } on ApiError catch (e) {
      if (e.status != 404) rethrow;
      await widget.store.loadProfile();
      hasReturning = false;
      active = false;
      return;
    }
    hasReturning =
        p.containsKey(ShopperProfile.key(widget.store.api.settings.userId)) ||
            p.getString('niche.activeUser') != null;
    active = p.getBool('niche.signedOut') != true &&
        (p.getString('niche.activeUser') == widget.store.api.settings.userId ||
            widget.store.profile.completed);
  }

  Future<void> enter({bool create = false, bool test = false}) async {
    String? displayName;
    if (create) {
      displayName = await showDialog<String>(
          context: context, builder: (_) => const _NewAccountDialog());
      if (displayName == null) return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      var id = widget.store.api.settings.userId;
      if (test) {
        id = 'u_demo';
      }
      if (create) {
        id = widget.store.demo
            ? 'local_${DateTime.now().microsecondsSinceEpoch}'
            : (await widget.store.api.createUser(displayName: displayName!)).id;
      }
      final settings = widget.store.api.settings.copyWith(userId: id);
      await Config.save(settings);
      widget.store.api.settings = settings;
      await widget.store.loadProfile(fromServer: !widget.store.demo);
      if (test && widget.store.demo && !widget.store.profile.completed) {
        await const ShopperProfile(
            completed: true, usualSize: 'M', usualSizes: {'top': 'M'}).save(id);
        await widget.store.loadProfile(fromServer: !widget.store.demo);
      }
      if (test && !widget.store.profile.completed) {
        await widget.store.profile.withCompletion(true).save(id);
        await widget.store.loadProfile();
      }
      final p = await SharedPreferences.getInstance();
      await p.setBool('niche.signedOut', false);
      await p.setString('niche.activeUser', id);
      hasReturning = true;
      if (mounted) setState(() => active = true);
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Could not open your profile. Check your connection and retry.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<void>(
      future: ready,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Scaffold(
              body: Center(
                  child: TextButton(
                      onPressed: reload,
                      child:
                          const Text('Could not load your profile. Retry'))));
        }
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
              body: Center(child: CircularProgressIndicator()));
        }
        if (!active) {
          return FeaturePage(
              title: 'Welcome',
              child: ListView(padding: const EdgeInsets.all(24), children: [
                Text('Find your next favorite fit',
                    style: Theme.of(context).textTheme.headlineMedium),
                const SizedBox(height: 16),
                const Text(
                    'Login reopens the profile saved on this device. Google sign-in is coming later.'),
                const SizedBox(height: 24),
                FilledButton(
                    onPressed: busy || !hasReturning ? null : () => enter(),
                    child: const Text('Login')),
                OutlinedButton(
                    onPressed: busy ? null : () => enter(create: true),
                    child: const Text('New account')),
                TextButton(
                    onPressed: busy ? null : () => enter(test: true),
                    child: const Text('Use team test profile')),
                if (widget.store.demo)
                  const Text(
                      'Sample mode: new profiles stay on this device until you connect.'),
                if (error != null) Text(error!),
              ]));
        }
        if (!widget.store.profile.completed) {
          return OnboardingScreen(
              api: widget.store.api,
              firstRun: true,
              demo: widget.store.demo,
              onSaved: () async {
                await widget.store.loadProfile(fromServer: !widget.store.demo);
                if (mounted) setState(() {});
              });
        }
        return ShopShell(key: widget.shellKey, store: widget.store);
      });
}

class ShopShell extends StatefulWidget {
  const ShopShell({super.key, required this.store});
  final StoreController store;
  @override
  State<ShopShell> createState() => _ShopShellState();
}

class _ShopShellState extends State<ShopShell> {
  int tab = 0;
  RankedProduct? seed;
  String? discoverQuery;
  int feedRevision = 0;
  List<RankedProduct>? seeded;
  String? seedError;
  int seedGeneration = 0;
  void clearSeed() => setState(() {
        seed = null;
        seeded = null;
        seedError = null;
        seedGeneration++;
        feedRevision++;
      });
  StoreController get store => widget.store;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) store.load();
    });
  }

  void openProducts(List<RankedProduct> products) {
    if (products.isEmpty) return;
    Navigator.of(context).popUntil((r) => r.isFirst);
    final request = ++seedGeneration;
    setState(() {
      seed = products.first;
      seeded = null;
      seedError = null;
      tab = 0;
      feedRevision++;
    });
    if (!store.demo) {
      store.api.feed(seed: products.first.id).then((cards) {
        if (mounted && request == seedGeneration) {
          setState(() => seeded = cards);
        }
      }).catchError((Object e) {
        if (mounted && request == seedGeneration) {
          setState(() => seedError = 'Could not load similar items. Retry.');
        }
      });
    }
  }

  void searchTag(String query) {
    Navigator.of(context).popUntil((r) => r.isFirst);
    setState(() {
      discoverQuery = query;
      tab = 1;
    });
  }

  Future<void> editSizing() async {
    await Navigator.push<void>(
        context,
        MaterialPageRoute(
            builder: (_) => OnboardingScreen(
                api: store.api,
                demo: store.demo,
                initialStep: 4,
                onSaved: () async {
                  await store.loadProfile(fromServer: !store.demo);
                  await store.load();
                })));
    await store.loadProfile(fromServer: !store.demo);
    if (mounted) setState(() {});
  }

  void completeLook(String id) => Navigator.push<void>(
      context,
      MaterialPageRoute(
          builder: (_) => CompleteLookScreen(
              api: store.api,
              productId: id,
              onProduct: (product) =>
                  openProducts([RankedProduct(product: product)]))));
  List<RankedProduct> get home {
    if (seed == null) return store.feed;
    if (!store.demo) return seeded ?? [seed!];
    final rest = store.feed.where((p) => p.id != seed!.id).toList();
    rest.sort((a, b) => (b.product.category == seed!.product.category ? 1 : 0)
        .compareTo(a.product.category == seed!.product.category ? 1 : 0));
    return [seed!, ...rest];
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        return Scaffold(
          extendBody: true,
          body: Column(children: [
            if (store.demo)
              Material(
                  color: const Color(0xFFF0E5E5),
                  child: ListTile(
                      dense: true,
                      title: const Text(
                          'Demo mode · sample catalog and local cart'))),
            if (store.accountWarning != null)
              ListTile(
                  title: Text(store.accountWarning!),
                  trailing: TextButton(
                      onPressed: store.load, child: const Text('Retry'))),
            Expanded(
                child: Center(
                    child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 540),
                        child: tab == 2
                            ? SocialFeed(
                                store: store,
                                onShop: openProducts,
                                onTagSearch: searchTag)
                            : tab == 1
                                ? DiscoverScreen(
                                    initialQuery: discoverQuery,
                                    store: store,
                                    onOpen: (p) => openProducts([p]))
                                : Column(children: [
                                    if (seed != null)
                                      Padding(
                                          padding: const EdgeInsets.all(8),
                                          child: InputChip(
                                              label: Text(
                                                  'Similar to: ${seed!.product.name}'),
                                              onPressed: clearSeed,
                                              deleteButtonTooltipMessage:
                                                  'Show all products',
                                              onDeleted: clearSeed)),
                                    if (seedError != null && seed != null)
                                      TextButton(
                                          onPressed: () =>
                                              openProducts([seed!]),
                                          child: Text(seedError!)),
                                    Expanded(
                                        child: store.loading
                                            ? const Center(
                                                child:
                                                    CircularProgressIndicator())
                                            : store.error != null
                                                ? Center(
                                                    child: TextButton(
                                                        onPressed: store.load,
                                                        child:
                                                            Text(store.error!)))
                                                : QuickBrowse(
                                                    key: ValueKey(
                                                        'home-$feedRevision'),
                                                    products: home
                                                        .map(browseMap)
                                                        .toList(),
                                                    savedIds: store.saved,
                                                    onSave: store.save,
                                                    onAddToCart: store.add,
                                                    imageUrl: store.imageUrl,
                                                    automaticSizing: true,
                                                    hasSizingProfile:
                                                        store.hasSizingData,
                                                    sizingRevision:
                                                        store.sizingRevision,
                                                    onSizeAdvice:
                                                        store.automaticSize,
                                                    onSizingSetup: editSizing,
                                                    onTryOn: store.demo
                                                        ? null
                                                        : (id) => requestTryOn(
                                                            context,
                                                            store.api,
                                                            id),
                                                    onCompleteLook: store.demo
                                                        ? null
                                                        : completeLook)),
                                  ])))),
          ]),
          bottomNavigationBar: SafeArea(
              minimum: const EdgeInsets.fromLTRB(28, 8, 28, 14),
              child: Center(
                  heightFactor: 1,
                  child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 440),
                      child: Material(
                          elevation: 8,
                          borderRadius: BorderRadius.circular(32),
                          clipBehavior: Clip.antiAlias,
                          child: NavigationBar(
                              height: 68,
                              selectedIndex: tab,
                              onDestinationSelected: (value) =>
                                  setState(() => tab = value),
                              destinations: const [
                                NavigationDestination(
                                    icon: Icon(Icons.home_outlined),
                                    label: 'Home'),
                                NavigationDestination(
                                    icon: Icon(Icons.explore_outlined),
                                    label: 'Discover'),
                                NavigationDestination(
                                    icon: Icon(Icons.people_outline),
                                    label: 'Inspo'),
                              ]))))),
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

class _NewAccountDialog extends StatefulWidget {
  const _NewAccountDialog();
  @override
  State<_NewAccountDialog> createState() => _NewAccountDialogState();
}

class _NewAccountDialogState extends State<_NewAccountDialog> {
  final name = TextEditingController();
  @override
  void dispose() {
    name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
          title: const Text('New account'),
          content: TextField(
              controller: name,
              decoration:
                  const InputDecoration(labelText: 'Your display name')),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () {
                  if (name.text.trim().isNotEmpty) {
                    Navigator.pop(context, name.text.trim());
                  }
                },
                child: const Text('Create profile'))
          ]);
}

import 'features/feed/reels_bindings.dart';
import 'package:flutter/services.dart';
import 'features/shared/niche_theme.dart';
import 'features/shared/niche_shell.dart';
import 'features/shared/niche_icons.dart';
import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'features/profile/shopper_profile.dart';
import 'features/profile/body_photo_card.dart';

import 'core/api.dart';
import 'features/auth/google_auth.dart';
import 'core/config.dart';
import 'core/models.dart';
import 'features/feed/reels_browse.dart';
import 'features/social/social_feed.dart';
import 'features/discover/discover_screen.dart';
import 'features/closet/closet_screen.dart';
import 'features/shared/feature_ui.dart';
import 'features/profile/profile_screen.dart';
import 'features/profile/onboarding_screen.dart';
import 'features/product/try_on.dart' show BodyPhotoButton;
import 'features/product/complete_look_screen.dart';
import 'features/store/cart_screen.dart';
import 'features/store/store_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      statusBarBrightness: Brightness.light,
      systemNavigationBarColor: Colors.transparent,
      systemNavigationBarIconBrightness: Brightness.dark));
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
  final routes = _RouteTracker();
  void openTop(String name, Widget page) {
    if (routes.top?.settings.name == name) return;
    navigation.currentState?.popUntil((r) => r.isFirst);
    navigation.currentState?.push(MaterialPageRoute<void>(
        settings: RouteSettings(name: name), builder: (_) => page));
  }

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

  /// Attach a Google account to the profile in use (a team account), once; afterwards it signs in with Google.
  Future<void> linkGoogle(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final idToken = await GoogleAuth.idToken();
      if (idToken == null) return;
      final session = await store.api.signInWithGoogle(idToken, linkUserId: store.api.settings.userId);
      await Config.save(store.api.settings.copyWith(userId: session.user.id, sessionToken: session.token));
      messenger.showSnackBar(const SnackBar(content: Text('Google account linked')));
      if (mounted) setState(() {});
    } on ApiError catch (e) {
      messenger.showSnackBar(SnackBar(
          content: Text(e.status == 409 ? 'That Google account or profile is already linked.' : e.message)));
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('Could not link Google. Try again.')));
    }
  }

  void user() => openTop(
      'User',
      FeaturePage(
          title: 'You',
          child: ListView(padding: const EdgeInsets.all(20), children: [
            for (final section in [
              ('Your style', 1),
              ('Shop for', 7),
              ('Stores you like', 2),
              ('Body scan', 3),
              ('Measurements & size', 4),
              ('Price preferences', 5)
            ])
              ListTile(
                  title: Text(section.$1),
                  trailing: const Icon(NicheIcons.chevronRight),
                  onTap: () => open(OnboardingScreen(
                      api: store.api,
                      demo: store.demo,
                      initialStep: section.$2,
                      onConnect: () =>
                          connectForSetup(navigation.currentContext!, store),
                      onSaved: () async {
                        await store.loadProfile(fromServer: !store.demo);
                        await store.load();
                      }))),
            if (!store.demo)
              ListTile(
                  title: const Text('Style DNA'),
                  trailing: const Icon(NicheIcons.chevronRight),
                  onTap: () => open(ProfileScreen(
                      api: store.api,
                      onChanged: () async {
                        await store.loadProfile(fromServer: !store.demo);
                        await store.load();
                      }))),
            ListTile(
                title: const Text('Orders'),
                leading: const Icon(NicheIcons.receiptLongOutlined),
                onTap: store.demo
                    ? null
                    : () => open(OrderHistory(api: store.api))),
            ListTile(
                title: const Text('Connection settings'),
                leading: const Icon(NicheIcons.tune),
                onTap: settings),
            if (!store.demo)
              ListTile(
                  title: const Text('Private scan & try-on photo'),
                  leading: const Icon(NicheIcons.lockOutline),
                  onTap: () => open(BodyPhotoCard(api: store.api))),
            if (GoogleAuth.available && !store.demo && store.api.settings.sessionToken.isEmpty)
              ListTile(
                  key: const ValueKey('link-google'),
                  title: const Text('Link Google account'),
                  subtitle: const Text('Sign in to this profile with Google from now on'),
                  leading: const Icon(NicheIcons.personOutline),
                  onTap: () => linkGoogle(navigation.currentContext!)),
            ListTile(
                title: const Text('Log out on this device'),
                leading: const Icon(NicheIcons.logout),
                onTap: () async {
                  if (store.api.settings.sessionToken.isNotEmpty) {
                    try {
                      await store.api.logout(); // the token stops working on the server too
                    } catch (_) {/* offline: forgetting it locally is enough */}
                    await Config.save(store.api.settings.copyWith(sessionToken: ''));
                    await GoogleAuth.signOut();
                  }
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
                                    onPressed: () =>
                                        Navigator.pop(context, false),
                                    child: const Text('Cancel')),
                                FilledButton(
                                    onPressed: () =>
                                        Navigator.pop(context, true),
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
      navigatorObservers: [routes],
      scrollBehavior: const MaterialScrollBehavior().copyWith(dragDevices: {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.trackpad,
        PointerDeviceKind.stylus,
      }),
      title: 'Niche',
      debugShowCheckedModeBanner: false,
      theme: Niche.theme,
      darkTheme: Niche.darkTheme,
      themeMode: ThemeMode.system,
      builder: (context, child) => NicheInsets(
          bottom: MediaQuery.viewPaddingOf(context).bottom,
          child: AnnotatedRegion<SystemUiOverlayStyle>(
              value: Niche.overlay(context),
              child: ColoredBox(
                  color: Niche.of(context).cream,
                  child: Overlay.wrap(
                      child: Stack(children: [
                    Positioned.fill(
                        top: MediaQuery.paddingOf(context).top + 56,
                        child: MediaQuery.removePadding(
                            context: context,
                            removeTop: true,
                            child: child ?? const SizedBox.shrink())),
                    Positioned(
                        top: 0,
                        left: 0,
                        right: 0,
                        child: AnimatedBuilder(
                            animation: store,
                            builder: (context, _) => NicheHeader(
                                count: store.cart.count,
                                initial: store.displayName,
                                onLiked: () => openTop('Liked',
                                    LikedScreen(store: store, onOpen: seed)),
                                onCart: () =>
                                    openTop('Cart', CartScreen(store: store)),
                                onCloset: () => openTop(
                                    'Closet',
                                    store.demo
                                        ? const FeaturePage(
                                            title: 'Closet',
                                            child: Center(
                                                child: Text(
                                                    'Connect your account to digitize your closet.')))
                                        : ClosetScreen(
                                            api: store.api,
                                            store: store,
                                            onProduct: seed)),
                                onUser: user)))
                  ]))))),
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
            (hasReturning && widget.store.profile.completed));
  }

  /// Team accounts until real sign-in lands: one tap opens that person's server profile.
  static const teamAccounts = [
    ('Adam', 'u_adam'),
    ('Nabil', 'u_nabil'),
    ('Ryan', 'u_ryan'),
  ];

  Future<void> enter(
      {bool create = false, bool test = false, String? asUser}) async {
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
      if (asUser != null) {
        id = asUser;
        test = true; // same completion handling as the test profile
      }
      if (test && asUser == null) {
        id = 'u_demo';
      }
      if (create) {
        id = widget.store.demo
            ? 'local_${DateTime.now().microsecondsSinceEpoch}'
            : (await widget.store.api.createUser(displayName: displayName!)).id;
      }
      final settings = widget.store.api.settings.copyWith(userId: id, sessionToken: '');
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

  /// Continue with Google: Google's account picker -> POST /auth/google -> our session token. A new Google
  /// user lands in onboarding (their profile isn't completed yet); a returning one goes straight in.
  Future<void> google() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final idToken = await GoogleAuth.idToken();
      if (idToken == null) return; // cancelled in Google's sheet
      final session = await widget.store.api.signInWithGoogle(idToken);
      final settings =
          widget.store.api.settings.copyWith(userId: session.user.id, sessionToken: session.token);
      await Config.save(settings);
      widget.store.api.settings = settings;
      await widget.store.loadProfile(fromServer: true);
      final p = await SharedPreferences.getInstance();
      await p.setBool('niche.signedOut', false);
      await p.setString('niche.activeUser', session.user.id);
      hasReturning = true;
      if (mounted) setState(() => active = true);
    } on ApiError catch (e) {
      if (mounted) setState(() => error = 'Google sign-in failed: ${e.message}');
    } catch (_) {
      if (mounted) setState(() => error = 'Google sign-in failed. Check your connection and retry.');
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
                Text(GoogleAuth.available && !widget.store.demo
                    ? 'Sign in with Google to keep your closet, fits and cart on every device.'
                    : 'Login reopens the profile saved on this device.'),
                const SizedBox(height: 24),
                if (GoogleAuth.available && !widget.store.demo) ...[
                  FilledButton.icon(
                      key: const ValueKey('google-sign-in'),
                      onPressed: busy ? null : google,
                      icon: const Icon(NicheIcons.personOutline),
                      label: const Text('Continue with Google')),
                  const SizedBox(height: 24),
                ],
                if (!widget.store.demo) ...[
                  Text('Who are you?',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (final (name, id) in teamAccounts)
                      FilledButton.tonal(
                          key: ValueKey('team-$id'),
                          onPressed: busy ? null : () => enter(asUser: id),
                          child: Text(name)),
                  ]),
                  const SizedBox(height: 16),
                ],
                FilledButton(
                    onPressed: busy || !hasReturning ? null : () => enter(),
                    child: const Text('Login')),
                OutlinedButton(
                    onPressed: busy ? null : () => enter(create: true),
                    child: const Text('New account')),
                TextButton.icon(
                    onPressed: () async {
                      await connectForSetup(context, widget.store);
                      if (mounted) reload();
                    },
                    icon: const Icon(NicheIcons.link),
                    label: const Text('Connect to the live app')),
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
              onConnect: () => connectForSetup(context, widget.store),
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
  final tabs = PageController();
  void changeTab(int value) {
    if (!mounted) return;
    setState(() => tab = value);
    if (tabs.hasClients) {
      tabs.animateToPage(value,
          duration: Niche.reduced(context) ? Duration.zero : Niche.duration,
          curve: Curves.easeInOutCubicEmphasized);
    }
  }

  @override
  void dispose() {
    tabs.dispose();
    super.dispose();
  }

  RankedProduct? seed;
  String? discoverQuery;
  int feedRevision = 0;
  List<RankedProduct>? seeded;
  String? seedError;
  int seedGeneration = 0;
  bool seedWasShown = false;
  Future<void> refreshHome() async {
    if (seed == null || store.demo) {
      await store.load();
      return;
    }
    final selected = seed!;
    final request = ++seedGeneration;
    try {
      final cards =
          await store.api.feed(seed: selected.id, seedShown: seedWasShown);
      if (mounted && request == seedGeneration) {
        setState(() {
          seeded = cards;
          seedWasShown = true;
          seedError = null;
          feedRevision++;
        });
      }
    } catch (_) {
      if (mounted && request == seedGeneration) {
        setState(() => seedError = 'Could not load similar items. Retry.');
      }
    }
  }

  void clearSeed() => setState(() {
        seed = null;
        seedWasShown = false;
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
      seedWasShown = true;
      seeded = null;
      seedError = null;
      tab = 0;
      feedRevision++;
    });
    changeTab(0);
    if (!store.demo) {
      store.api.feed(seed: products.first.id).then((cards) {
        if (mounted && request == seedGeneration) {
          setState(() {
            seeded = cards;
            seedWasShown = true;
          });
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
    changeTab(1);
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

  Future<void> openBodyPhoto() async {
    await showModalBottomSheet<void>(
        context: context,
        useSafeArea: true,
        builder: (_) => Padding(
            padding: const EdgeInsets.all(24),
            child: BodyPhotoButton(api: store.api)));
    if (mounted) await refreshHome();
  }

  Future<void> openClosetPiece(String? id) async {
    if (store.demo || id == null) {
      await Navigator.push<void>(
          context,
          MaterialPageRoute(
              builder: (_) => store.demo
                  ? const FeaturePage(
                      title: 'Closet',
                      child: Center(
                          child: Text(
                              'Connect your account to digitize your closet.')))
                  : ClosetScreen(
                      api: store.api,
                      store: store,
                      onProduct: (p) => openProducts([p]))));
      if (mounted && !store.demo) await refreshHome();
      return;
    }
    try {
      final pieces = await store.api.closet();
      if (!mounted) return;
      final matches = pieces.where((p) => p.id == id);
      await Navigator.push<void>(
          context,
          MaterialPageRoute(
              builder: (_) => matches.isEmpty
                  ? ClosetScreen(
                      api: store.api,
                      store: store,
                      onProduct: (p) => openProducts([p]))
                  : ClosetPieceScreen(api: store.api, initial: matches.first)));
      if (mounted) await refreshHome();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Could not open your closet. Try again.')));
      }
    }
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
                  color: Niche.of(context).blush,
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
                        child: PageView(
                            controller: tabs,
                            physics: const ClampingScrollPhysics(),
                            onPageChanged: (value) {
                              Niche.select();
                              setState(() => tab = value);
                            },
                            children: [
                              Column(children: [
                                if (seedError != null && seed != null)
                                  TextButton(
                                      onPressed: refreshHome,
                                      child: Text(seedError!)),
                                Expanded(
                                    child: store.loading
                                        ? const Center(
                                            child: CircularProgressIndicator())
                                        : store.error != null
                                            ? Center(
                                                child: TextButton(
                                                    onPressed: store.load,
                                                    child: Text(store.error!)))
                                            : ReelsBrowse(
                                                key: ValueKey(
                                                    'home-$feedRevision'),
                                                active: tab == 0,
                                                products: home
                                                    .map(browseMap)
                                                    .toList(),
                                                savedIds: store.saved,
                                                prepareTryOns: store.demo
                                                    ? null
                                                    : ReelsBindings(store.api)
                                                        .prepare,
                                                loadTryOns: store.demo
                                                    ? null
                                                    : ReelsBindings(store.api)
                                                        .load,
                                                onSave: store.save,
                                                onAddToCart: store.add,
                                                imageUrl: store.imageUrl,
                                                onSizeAdvice:
                                                    store.automaticSize,
                                                onRefresh: refreshHome,
                                                seedLabel: seed?.product.name,
                                                onClearSeed: clearSeed,
                                                onCloset: openClosetPiece,
                                                onBodyPhoto: store.demo
                                                    ? null
                                                    : openBodyPhoto)),
                              ]),
                              DiscoverScreen(
                                  key: ValueKey('discover-$discoverQuery'),
                                  initialQuery: discoverQuery,
                                  store: store,
                                  onOpen: (p) => openProducts([p])),
                              SocialFeed(
                                  store: store,
                                  onShop: openProducts,
                                  onTagSearch: searchTag),
                            ])))),
          ]),
          bottomNavigationBar:
              NicheNavigation(controller: tabs, index: tab, onTap: changeTab),
        );
      });
}

class ProductPhoto extends StatelessWidget {
  const ProductPhoto({super.key, required this.url, required this.name});
  final String url;
  final String name;
  @override
  Widget build(BuildContext context) => ColoredBox(
      color: Niche.of(context).stone,
      child: url.isEmpty
          ? const Center(child: Icon(NicheIcons.imageOutlined))
          : Image.network(url,
              fit: BoxFit.contain,
              webHtmlElementStrategy: WebHtmlElementStrategy.prefer,
              semanticLabel: name,
              errorBuilder: (_, error, stack) => const Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Icon(NicheIcons.imageOutlined),
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

class _RouteTracker extends NavigatorObserver {
  Route<dynamic>? top;
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    top = route;
  }

  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) {
    top = previousRoute;
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    top = newRoute;
  }
}

Future<bool> connectForSetup(
    BuildContext context, StoreController store) async {
  await Navigator.push<void>(context,
      MaterialPageRoute(builder: (_) => ConnectionScreen(store: store)));
  if (store.demo) return false;
  try {
    try {
      await store.api.getUser();
    } on ApiError catch (e) {
      if (e.status != 404 || !store.api.settings.userId.startsWith('local_')) {
        return false;
      }
      await store.api.createUser(
          id: store.api.settings.userId, displayName: 'Your profile');
    }
    return true;
  } catch (_) {
    return false;
  }
}

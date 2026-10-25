import 'niche_icons.dart';
import 'dart:ui';
import 'package:animations/animations.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

abstract final class Niche {
  static const cream = Color(0xFFFFFBF0),
      paper = Color(0xFFFBF3EE),
      merlot = Color(0xFF5B1F33),
      wine = Color(0xFF722F42),
      hook = Color(0xFFE9B9A8),
      blush = Color(0xFFF0E5E5),
      stone = Color(0xFFEDEAE4),
      ink = Color(0xFF1E1517),
      muted = Color(0xFF7A6A6E);
  static const gutter = 16.0, radius = 28.0, navHeight = 60.0;
  static const wordmark = TextStyle(
      fontFamily: 'YoungSerif',
      fontSize: 28,
      height: 1,
      letterSpacing: -.28,
      color: merlot,
      fontWeight: FontWeight.w400);
  static const price = TextStyle(
      fontFamily: 'Manrope',
      fontSize: 17,
      height: 20 / 17,
      fontWeight: FontWeight.w700,
      fontFeatures: [FontFeature.tabularFigures()]);
  static const duration = Duration(milliseconds: 300);
  static double bottomSpace(BuildContext context) =>
      navHeight + 26 + NicheInsets.systemBottom(context);
  static bool reduced(BuildContext context) =>
      MediaQuery.disableAnimationsOf(context);
  static void select() => HapticFeedback.selectionClick();
  static TextStyle ui(double size, double line, FontWeight weight) => TextStyle(
      fontFamily: 'Manrope',
      fontSize: size,
      height: line / size,
      fontWeight: weight,
      color: ink);
  static TextStyle display(double size, double line) => TextStyle(
      fontFamily: 'YoungSerif',
      fontSize: size,
      height: line / size,
      fontWeight: FontWeight.w400,
      color: merlot);
  static ThemeData get theme {
    final text = TextTheme(
        displayLarge: display(40, 46),
        displayMedium: display(38, 44),
        displaySmall: display(34, 40),
        headlineLarge: display(30, 36),
        headlineMedium: display(28, 34),
        headlineSmall: display(24, 30),
        titleLarge: ui(20, 26, FontWeight.w600),
        titleMedium: ui(17, 22, FontWeight.w600),
        titleSmall: ui(15, 20, FontWeight.w600),
        bodyLarge: ui(16, 24, FontWeight.w400),
        bodyMedium: ui(14, 20, FontWeight.w400),
        bodySmall: ui(12, 18, FontWeight.w400),
        labelLarge: ui(15, 20, FontWeight.w700),
        labelMedium: ui(14, 20, FontWeight.w600),
        labelSmall: ui(11, 14, FontWeight.w700).copyWith(letterSpacing: 1.32));
    return ThemeData(
        useMaterial3: true,
        fontFamily: 'Manrope',
        textTheme: text,
        scaffoldBackgroundColor: cream,
        colorScheme: const ColorScheme.light(
            primary: wine,
            secondary: merlot,
            surface: cream,
            onSurface: ink,
            onPrimary: Colors.white,
            onSecondary: cream,
            surfaceContainerHighest: blush,
            outline: muted),
        splashFactory: NoSplash.splashFactory,
        iconTheme: const IconThemeData(color: merlot, size: 23),
        pageTransitionsTheme: const PageTransitionsTheme(builders: {
          TargetPlatform.android: NichePageTransition(),
          TargetPlatform.iOS: NichePageTransition(),
          TargetPlatform.macOS: NichePageTransition(),
          TargetPlatform.windows: NichePageTransition(),
          TargetPlatform.linux: NichePageTransition()
        }),
        appBarTheme: AppBarTheme(
            backgroundColor: cream,
            surfaceTintColor: Colors.transparent,
            scrolledUnderElevation: 0,
            centerTitle: false,
            titleTextStyle: text.headlineSmall,
            systemOverlayStyle: SystemUiOverlayStyle.dark,
            elevation: 0),
        cardTheme: CardThemeData(
            color: paper,
            elevation: 0,
            margin: const EdgeInsets.symmetric(vertical: 6),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(radius))),
        bottomSheetTheme: BottomSheetThemeData(
            backgroundColor: paper,
            surfaceTintColor: Colors.transparent,
            modalBarrierColor: ink.withValues(alpha: .30),
            shape: const RoundedRectangleBorder(
                borderRadius:
                    BorderRadius.vertical(top: Radius.circular(radius)))),
        dialogTheme: DialogThemeData(
            backgroundColor: paper,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(radius))),
        filledButtonTheme: FilledButtonThemeData(
            style: FilledButton.styleFrom(
                minimumSize: const Size(48, 52),
                backgroundColor: wine,
                foregroundColor: Colors.white,
                textStyle: text.labelLarge,
                shape: const StadiumBorder(),
                elevation: 0)),
        outlinedButtonTheme: OutlinedButtonThemeData(
            style: OutlinedButton.styleFrom(
                minimumSize: const Size(48, 52),
                foregroundColor: merlot,
                textStyle: text.labelLarge,
                side: BorderSide(color: merlot.withValues(alpha: .25)),
                shape: const StadiumBorder())),
        textButtonTheme: TextButtonThemeData(
            style: TextButton.styleFrom(
                foregroundColor: wine,
                textStyle: text.labelMedium,
                minimumSize: const Size(44, 44))),
        chipTheme: ChipThemeData(
            backgroundColor: Colors.transparent,
            selectedColor: merlot,
            secondarySelectedColor: merlot,
            labelStyle: text.bodyMedium,
            secondaryLabelStyle: text.bodyMedium!.copyWith(color: paper),
            checkmarkColor: paper,
            shape: const StadiumBorder(),
            side: BorderSide(color: merlot.withValues(alpha: .14)),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8)),
        inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: paper,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(24),
                borderSide: BorderSide(color: merlot.withValues(alpha: .14))),
            enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(24),
                borderSide: BorderSide(color: merlot.withValues(alpha: .14)))),
        dividerTheme: DividerThemeData(
            color: merlot.withValues(alpha: .12), thickness: .7),
        progressIndicatorTheme: const ProgressIndicatorThemeData(
            color: wine, linearTrackColor: blush));
  }
}

class NichePageTransition extends PageTransitionsBuilder {
  const NichePageTransition();
  @override
  Widget buildTransitions<T>(
          PageRoute<T> route,
          BuildContext context,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
          Widget child) =>
      Niche.reduced(context)
          ? FadeTransition(opacity: animation, child: child)
          : SharedAxisTransition(
              animation: animation,
              secondaryAnimation: secondaryAnimation,
              transitionType: SharedAxisTransitionType.horizontal,
              fillColor: Niche.cream,
              child: child);
}

class NicheGlass extends StatelessWidget {
  const NicheGlass(
      {super.key,
      required this.child,
      this.radius = 28,
      this.opacity = .7,
      this.blur = 20});
  final Widget child;
  final double radius, opacity, blur;
  @override
  Widget build(BuildContext context) => ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: blur, sigmaY: blur),
          child: DecoratedBox(
              decoration: BoxDecoration(
                  color: Niche.cream.withValues(alpha: opacity),
                  borderRadius: BorderRadius.circular(radius),
                  border: Border.all(
                      color: Niche.paper.withValues(alpha: .4), width: .5)),
              child: child)));
}

class NichePress extends StatefulWidget {
  const NichePress({super.key, required this.child});
  final Widget child;
  @override
  State<NichePress> createState() => _NichePressState();
}

class _NichePressState extends State<NichePress> {
  bool down = false;
  @override
  Widget build(BuildContext context) => Listener(
      onPointerDown: (_) => setState(() => down = true),
      onPointerUp: (_) {
        if (down) setState(() => down = false);
      },
      onPointerCancel: (_) => setState(() => down = false),
      child: AnimatedScale(
          scale: down && !Niche.reduced(context) ? .96 : 1,
          duration: Duration(milliseconds: down ? 120 : 180),
          curve: Curves.easeOutBack,
          child: widget.child));
}

class NicheChip extends StatelessWidget {
  const NicheChip(
      {super.key,
      required this.label,
      required this.selected,
      required this.onSelected});
  final String label;
  final bool selected;
  final ValueChanged<bool>? onSelected;
  @override
  Widget build(BuildContext context) => NichePress(
      child: Semantics(
          selected: selected,
          child: InkWell(
              borderRadius: BorderRadius.circular(999),
              onTap: onSelected == null
                  ? null
                  : () {
                      Niche.select();
                      onSelected!(!selected);
                    },
              child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  curve: Curves.easeOutCubic,
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                  decoration: BoxDecoration(
                      color: selected ? Niche.merlot : Niche.cream,
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(
                          color: Niche.merlot.withValues(alpha: .14))),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    AnimatedSize(
                        duration: const Duration(milliseconds: 180),
                        child: SizedBox(
                            width: selected ? 20 : 0,
                            child: selected
                                ? const Icon(NicheIcons.check,
                                    size: 15, color: Niche.paper)
                                : null)),
                    Text(label,
                        style: Theme.of(context).textTheme.bodyMedium!.copyWith(
                            color: selected ? Niche.paper : Niche.ink))
                  ])))));
}

/// Flutter's zero-duration AnimatedSize can relayout itself; reduced motion uses a fade instead.
class NicheReveal extends StatelessWidget {
  const NicheReveal({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => Niche.reduced(context)
      ? AnimatedSwitcher(
          duration: const Duration(milliseconds: 120), child: child)
      : AnimatedSize(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutCubic,
          child: child);
}

class NicheEntrance extends StatelessWidget {
  const NicheEntrance({super.key, required this.child, this.index = 0});
  final Widget child;
  final int index;
  @override
  Widget build(BuildContext context) {
    final millis = 280 + index * 40;
    return TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: 1),
        duration: Duration(milliseconds: Niche.reduced(context) ? 120 : millis),
        curve: Niche.reduced(context)
            ? Curves.linear
            : Interval(index * 40 / millis, 1, curve: Curves.easeOutCubic),
        child: child,
        builder: (context, value, child) => Opacity(
            opacity: value,
            child: Transform.translate(
                offset:
                    Offset(0, Niche.reduced(context) ? 0 : 10 * (1 - value)),
                child: child)));
  }
}

class NichePhotoDrop extends StatelessWidget {
  const NichePhotoDrop({super.key, required this.onTap, required this.label});
  final VoidCallback? onTap;
  final String label;
  @override
  Widget build(BuildContext context) => NichePress(
      child: Semantics(
          button: true,
          enabled: onTap != null,
          child: InkWell(
              borderRadius: BorderRadius.circular(28),
              onTap: onTap == null
                  ? null
                  : () {
                      Niche.select();
                      onTap!();
                    },
              child: CustomPaint(
                  foregroundPainter: const _DashedFrame(),
                  child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                          vertical: 30, horizontal: 20),
                      decoration: BoxDecoration(
                          color: Niche.paper,
                          borderRadius: BorderRadius.circular(28)),
                      child: Column(children: [
                        const Icon(NicheIcons.addAPhotoOutlined, size: 30),
                        const SizedBox(height: 12),
                        Text(label,
                            style: Theme.of(context).textTheme.titleMedium,
                            textAlign: TextAlign.center),
                        const SizedBox(height: 8),
                        Text('Head to toe, in good light.',
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium!
                                .copyWith(color: Niche.muted))
                      ]))))));
}

class _DashedFrame extends CustomPainter {
  const _DashedFrame();
  @override
  void paint(Canvas canvas, Size size) {
    final path = Path()
      ..addRRect(RRect.fromRectAndRadius(
          Offset.zero & size, const Radius.circular(28)));
    final paint = Paint()
      ..color = Niche.merlot.withValues(alpha: .25)
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    for (final metric in path.computeMetrics()) {
      for (double offset = 0; offset < metric.length; offset += 9) {
        canvas.drawPath(metric.extractPath(offset, offset + 5), paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DashedFrame oldDelegate) => false;
}

/// Preserve physical system insets before Scaffold consumes them for its body.
class NicheInsets extends InheritedWidget {
  const NicheInsets({super.key, required this.bottom, required super.child});
  final double bottom;
  static double systemBottom(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<NicheInsets>()?.bottom ??
      MediaQuery.viewPaddingOf(context).bottom;
  @override
  bool updateShouldNotify(covariant NicheInsets oldWidget) =>
      bottom != oldWidget.bottom;
}

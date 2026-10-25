import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dress_to_impress/features/shared/niche_theme.dart';

void main() {
  test('light and dark themes carry their tones', () {
    expect(Niche.theme.brightness, Brightness.light);
    expect(Niche.darkTheme.brightness, Brightness.dark);
    expect(Niche.theme.extension<NicheTones>(), NicheTones.light);
    expect(Niche.darkTheme.extension<NicheTones>(), NicheTones.dark);
    expect(Niche.darkTheme.scaffoldBackgroundColor, NicheTones.dark.cream);
    expect(Niche.darkTheme.textTheme.bodyMedium!.color, NicheTones.dark.ink);
    expect(Niche.darkTheme.textTheme.headlineSmall!.color,
        NicheTones.dark.brand);
  });

  testWidgets('Niche.of follows the active theme', (tester) async {
    late NicheTones seen;
    await tester.pumpWidget(MaterialApp(
        theme: Niche.theme,
        darkTheme: Niche.darkTheme,
        themeMode: ThemeMode.dark,
        home: Builder(builder: (context) {
          seen = Niche.of(context);
          return const SizedBox();
        })));
    expect(seen.isDark, isTrue);
    expect(seen.cream, NicheTones.dark.cream);
  });
}

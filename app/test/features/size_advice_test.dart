import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:dress_to_impress/core/api.dart';
import 'package:dress_to_impress/features/product/size_advice_sheet.dart';

void main() {
  testWidgets('size advice sends measurements and preserves jean size labels',
      (tester) async {
    final api = Api(client: MockClient((request) async {
      expect(request.url.path, '/size');
      final body = jsonDecode(request.body) as Map;
      expect(body['product_id'], 'jean');
      expect(body['height_cm'], 170);
      expect(body['weight_kg'], 65);
      expect(body['waist_in'], 30);
      return http.Response(
          jsonEncode({
            'size': '30/32',
            'confidence': 'medium',
            'reason': 'Based on your waist.'
          }),
          200);
    }));
    tester.view.physicalSize = const Size(440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: SizeAdviceSheet(api: api, productId: 'jean'))));
    await tester.enterText(
        find.widgetWithText(TextField, 'Waist (inches, optional)'), '30');
    await tester.tap(find.text('Recommend size'));
    await tester.pumpAndSettle();
    expect(find.text('Suggested size 30/32'), findsOneWidget);
    expect(find.text('medium confidence'), findsOneWidget);
  });
  testWidgets('size advice rejects invalid measurements without requesting',
      (tester) async {
    var requests = 0;
    final api = Api(client: MockClient((_) async {
      requests++;
      return http.Response('{}', 200);
    }));
    tester.view.physicalSize = const Size(440, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: SizeAdviceSheet(api: api, productId: 'top'))));
    await tester.enterText(find.widgetWithText(TextField, 'Height (cm)'), '-1');
    await tester.tap(find.text('Recommend size'));
    await tester.pump();
    expect(requests, 0);
    expect(find.textContaining('Enter positive'), findsOneWidget);
  });
}

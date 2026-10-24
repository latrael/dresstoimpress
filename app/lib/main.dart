import 'package:flutter/material.dart';

import 'core/api.dart';
import 'core/config.dart';

/// Minimal shell around the reference client: set the server URL + key, then test the connection.
/// The real app is Ryan's project; copy lib/core/ from here if useful.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Config.load();
  runApp(const MaterialApp(debugShowCheckedModeBanner: false, home: ConnectionScreen()));
}

class ConnectionScreen extends StatefulWidget {
  const ConnectionScreen({super.key});

  @override
  State<ConnectionScreen> createState() => _ConnectionScreenState();
}

class _ConnectionScreenState extends State<ConnectionScreen> {
  late final _base = TextEditingController(text: Config.current.baseUrl);
  late final _key = TextEditingController(text: Config.current.apiKey);
  String _status = '';
  bool _testing = false;

  @override
  void dispose() {
    _base.dispose();
    _key.dispose();
    super.dispose();
  }

  Future<void> _test() async {
    setState(() => _testing = true);
    await Config.save(Config.current.copyWith(baseUrl: _base.text, apiKey: _key.text));
    String status;
    try {
      await Api.instance.health();
      final cards = await Api.instance.feed(limit: 1);
      status = 'Connected. Feed works (${cards.length} card${cards.length == 1 ? '' : 's'}).';
    } catch (e) {
      status = 'Failed: $e';
    }
    if (mounted) {
      setState(() {
        _testing = false;
        _status = status;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('DressToImpress API check')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _base,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'Server URL'),
          ),
          TextField(
            controller: _key,
            obscureText: true,
            autocorrect: false,
            decoration: const InputDecoration(labelText: 'X-DTI-Key (sent privately, never committed)'),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _testing ? null : _test, child: Text(_testing ? 'Testing…' : 'Test connection')),
          const SizedBox(height: 12),
          Text(_status),
        ],
      ),
    );
  }
}

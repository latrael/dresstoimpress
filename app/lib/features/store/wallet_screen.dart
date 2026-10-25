import 'package:flutter/material.dart';

import '../../core/api.dart';
import '../../core/models.dart';
import '../shared/niche_theme.dart';
import 'cart_screen.dart' show dollars;

/// The Niche Card: your Capital One Nessie account and every store purchase, read live from Nessie
/// (GET /wallet/{user}). Spending is totalled from the purchases: the sandbox never lowers the balance.
class WalletScreen extends StatefulWidget {
  const WalletScreen({super.key, required this.api});
  final Api api;
  @override
  State<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends State<WalletScreen> {
  late Future<Wallet> wallet = widget.api.wallet();

  Future<void> refresh() async {
    final next = widget.api.wallet();
    setState(() => wallet = next);
    await next;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('Niche Card')),
      body: FutureBuilder<Wallet>(
          future: wallet,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                  child: TextButton(onPressed: refresh, child: const Text('Could not load your card. Retry')));
            }
            if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
            final w = snapshot.data!;
            final text = Theme.of(context).textTheme;
            return RefreshIndicator(
                onRefresh: refresh,
                child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
                  _Card(account: w.account),
                  const SizedBox(height: 20),
                  Row(children: [
                    _Stat(label: 'This month', value: dollars(w.spentMonthUsd)),
                    _Stat(label: 'All time', value: dollars(w.spentUsd)),
                    _Stat(label: 'Rewards', value: '${(w.account?.rewards ?? 0).round()} pts'),
                  ]),
                  if (!w.live && w.purchases.isNotEmpty)
                    Padding(
                        padding: const EdgeInsets.only(top: 16),
                        child: Text('Nessie is unreachable right now, so these are your saved receipts.',
                            style: text.bodySmall)),
                  const SizedBox(height: 24),
                  Text('Purchases', style: text.titleMedium),
                  const SizedBox(height: 8),
                  if (w.purchases.isEmpty)
                    Padding(
                        padding: const EdgeInsets.symmetric(vertical: 24),
                        child: Text('No purchases yet. Your first checkout opens your Niche Card.',
                            style: text.bodyMedium))
                  else
                    for (final p in w.purchases) _PurchaseRow(p: p),
                  const SizedBox(height: 24),
                  Text(
                      w.live
                          ? 'Live from the Capital One Nessie API. Sandbox: no real money moves.'
                          : 'Capital One Nessie sandbox: no real money moves.',
                      textAlign: TextAlign.center,
                      style: text.bodySmall),
                ]));
          }));
}

/// The card itself: merlot, the wordmark, the last four digits of the Nessie account.
class _Card extends StatelessWidget {
  const _Card({required this.account});
  final WalletAccount? account;
  @override
  Widget build(BuildContext context) => AspectRatio(
      aspectRatio: 1.586, // a real card's shape
      child: DecoratedBox(
          decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(24),
              gradient: const LinearGradient(
                  begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Niche.merlot, Niche.wine]),
              boxShadow: const [BoxShadow(color: Color(0x335B1F33), blurRadius: 24, offset: Offset(0, 10))]),
          child: Padding(
              padding: const EdgeInsets.all(22),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text('niche', style: Niche.wordmark.copyWith(color: Niche.cream)),
                  const Spacer(),
                  Text((account?.type ?? 'Credit Card').toUpperCase(),
                      style: Niche.ui(11, 14, FontWeight.w700, Niche.hook).copyWith(letterSpacing: 1.3)),
                ]),
                const Spacer(),
                Text(account == null ? 'Opens at your first checkout' : '••••  ••••  ••••  ${account!.last4}',
                    style: Niche.ui(18, 22, FontWeight.w600, Niche.cream).copyWith(letterSpacing: 1.5)),
                const SizedBox(height: 10),
                Text('Capital One Nessie · sandbox', style: Niche.ui(11, 14, FontWeight.w500, Niche.hook)),
              ]))));
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => Expanded(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label.toUpperCase(), style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 4),
        Text(value, style: Niche.price),
      ]));
}

class _PurchaseRow extends StatelessWidget {
  const _PurchaseRow({required this.p});
  final WalletPurchase p;
  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final pending = p.status == 'pending';
    return Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          CircleAvatar(
              radius: 20,
              backgroundColor: Niche.of(context).blush,
              child: Text(p.storeName.isEmpty ? '?' : p.storeName[0],
                  style: Niche.display(18, 20))),
          const SizedBox(width: 12),
          Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(p.storeName, style: text.titleSmall),
            if (p.items.isNotEmpty)
              Text(p.items.join(', '), maxLines: 2, overflow: TextOverflow.ellipsis, style: text.bodySmall),
            Text(
                [p.date, if (p.nessieId != null) 'Nessie #${p.nessieId!.substring(0, p.nessieId!.length.clamp(0, 8))}']
                    .join(' · '),
                style: text.labelSmall),
          ])),
          const SizedBox(width: 8),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(dollars(p.amountUsd), style: Niche.price),
            const SizedBox(height: 4),
            Text(pending ? 'Pending' : 'Paid',
                style: text.labelSmall!.copyWith(color: pending ? Niche.hook : Niche.wine)),
          ]),
        ]));
  }
}

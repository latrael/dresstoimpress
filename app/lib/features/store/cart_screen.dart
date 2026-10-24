import 'package:flutter/material.dart';

import '../../core/api.dart';
import '../../core/models.dart';
import 'store_controller.dart';

String retailerName(String retailer) => retailer == 'hm'
    ? 'H&M'
    : retailer == 'uniqlo'
        ? 'Uniqlo'
        : retailer;
String dollars(num value) => '\$${value.toStringAsFixed(2)}';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key, required this.store});
  final StoreController store;
  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  bool busy = false;
  String? error;
  Set<String> unavailable = {};
  CheckoutResult? receipt;

  Future<void> remove(CartItem item) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.store.remove(item.productId, item.size);
    } catch (_) {
      if (mounted) {
        setState(() => error = 'Could not remove this item. Please try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> checkout() async {
    final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: Text(widget.store.demo
                    ? 'Complete demo order?'
                    : 'Place sandbox order?'),
                content: Text(widget.store.demo
                    ? 'This only clears your demo cart. No payment is processed.'
                    : 'Place ${dollars(widget.store.cart.totalUsd)} through the team’s Nessie sandbox? This does not order from the retailers.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Keep browsing')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Place order'))
                ]));
    if (confirmed != true || !mounted) return;
    setState(() {
      busy = true;
      error = null;
      unavailable = {};
    });
    try {
      final result = await widget.store.checkout();
      if (mounted) setState(() => receipt = result);
    } on ApiError catch (e) {
      if (mounted) {
        setState(() {
          error = e.message;
          unavailable =
              e.unavailable.map((i) => '${i.productId}:${i.size}').toSet();
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Order status could not be confirmed. Check order history before trying again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final cart = widget.store.cart;
        return Scaffold(
            appBar: AppBar(
                title: Text(receipt == null ? 'Your cart' : 'Order receipt'),
                actions: [
                  if (!widget.store.demo)
                    IconButton(
                        tooltip: 'Order history',
                        onPressed: () => Navigator.push(
                            context,
                            MaterialPageRoute<void>(
                                builder: (_) =>
                                    OrderHistory(api: widget.store.api))),
                        icon: const Icon(Icons.receipt_long_outlined)),
                ]),
            body: Center(
                child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 540),
                    child:
                        ListView(padding: const EdgeInsets.all(20), children: [
                      if (receipt != null) ...[
                        Icon(
                            widget.store.demo
                                ? Icons.check_circle_outline
                                : Icons.receipt_long,
                            size: 48),
                        const SizedBox(height: 16),
                        Text(
                            widget.store.demo
                                ? 'Demo complete'
                                : 'Order ${receipt!.orderId}',
                            style: Theme.of(context).textTheme.headlineSmall),
                        if (widget.store.demo)
                          const Text('No payment was processed.'),
                        for (final p in receipt!.purchases)
                          ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text(retailerName(p.retailer)),
                              trailing: Text(dollars(p.amountUsd)),
                              subtitle: Text(p.status == 'paid'
                                  ? 'Paid in Nessie sandbox'
                                  : p.status == 'demo'
                                      ? 'Demo only'
                                      : p.status == 'pending_nessie'
                                          ? 'Payment pending — not paid'
                                          : 'Payment failed — check with the team before retrying')),
                        const SizedBox(height: 12),
                        Text('Total ${dollars(receipt!.totalUsd)}',
                            style: Theme.of(context).textTheme.titleLarge),
                      ] else if (cart.count == 0) ...[
                        const SizedBox(height: 80),
                        const Icon(Icons.shopping_bag_outlined, size: 48),
                        const SizedBox(height: 16),
                        const Center(
                            child:
                                Text('Your next favorite piece is waiting.')),
                        TextButton(
                            onPressed: () => Navigator.pop(context),
                            child: const Text('Back to browsing')),
                      ] else ...[
                        if (widget.store.demo)
                          const Text(
                              'DEMO CART · no payment will be processed'),
                        for (final group in cart.groups) ...[
                          const SizedBox(height: 24),
                          Text(retailerName(group.retailer),
                              style: Theme.of(context).textTheme.titleLarge),
                          for (final item in group.items)
                            ListTile(
                                contentPadding: EdgeInsets.zero,
                                title:
                                    Text(item.product?.name ?? item.productId),
                                subtitle: Text(
                                    'Size ${item.size} · Qty ${item.qty}${unavailable.contains('${item.productId}:${item.size}') ? ' · unavailable' : ''}'),
                                trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(dollars(
                                          (item.product?.effectivePrice ?? 0) *
                                              item.qty)),
                                      IconButton(
                                          tooltip:
                                              'Remove ${item.product?.name ?? 'item'} size ${item.size}',
                                          onPressed:
                                              busy ? null : () => remove(item),
                                          icon: const Icon(Icons.close))
                                    ])),
                          Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                  'Subtotal ${dollars(group.subtotalUsd)}')),
                          const Divider(height: 32),
                        ],
                        Text('Total ${dollars(cart.totalUsd)}',
                            style: Theme.of(context).textTheme.headlineSmall),
                        const SizedBox(height: 20),
                        if (error != null)
                          Padding(
                              padding: const EdgeInsets.only(bottom: 16),
                              child: Text(error!,
                                  style: TextStyle(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .error))),
                        FilledButton(
                            onPressed: busy ? null : checkout,
                            child: Text(busy
                                ? 'Please wait…'
                                : widget.store.demo
                                    ? 'Complete demo order'
                                    : 'Checkout in Nessie sandbox')),
                      ],
                    ]))));
      });
}

class OrderHistory extends StatefulWidget {
  const OrderHistory({super.key, required this.api});
  final Api api;
  @override
  State<OrderHistory> createState() => _OrderHistoryState();
}

class _OrderHistoryState extends State<OrderHistory> {
  late Future<List<Order>> orders = widget.api.orders();
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('Order history')),
      body: FutureBuilder<List<Order>>(
          future: orders,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return Center(
                  child: TextButton(
                      onPressed: () =>
                          setState(() => orders = widget.api.orders()),
                      child: const Text('Could not load orders. Retry')));
            }
            if (!snapshot.hasData) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.data!.isEmpty) {
              return const Center(child: Text('No orders yet.'));
            }
            return ListView(children: [
              for (final order in snapshot.data!)
                ExpansionTile(
                    title: Text('Order ${order.id}'),
                    subtitle: Text(dollars(order.totalUsd)),
                    children: [
                      for (final p in order.purchases)
                        ListTile(
                            title: Text(retailerName(p.retailer)),
                            subtitle: Text(p.status),
                            trailing: Text(dollars(p.amountUsd)))
                    ])
            ]);
          }));
}

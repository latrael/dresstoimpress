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

  @override
  void initState() {
    super.initState();
    busy = !widget.store.demo;
    widget.store.refreshCart().whenComplete(() {
      if (mounted) setState(() => busy = false);
    });
  }

  Future<void> retry(String retailer) async {
    final order = receipt;
    if (order == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final updated =
          await widget.store.api.retryOrder(order.orderId, retailer: retailer);
      if (mounted) setState(() => receipt = updated);
    } on ApiError catch (e) {
      if (mounted) {
        setState(() => error = e.status == 503
            ? 'Payments are not configured on this server.'
            : 'Retry could not be confirmed. Check order history before trying again.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Retry could not be confirmed. Check order history before trying again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> remove(CartItem item) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.store.remove(item.productId, item.size);
    } catch (_) {
      await widget.store.refreshCart();
      if (mounted) {
        setState(() => error = 'Could not remove this item. Please try again.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> editSize(CartItem item) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final product =
          item.product ?? await widget.store.api.product(item.productId);
      if (!mounted) return;
      final size = await showModalBottomSheet<String>(
          context: context,
          useSafeArea: true,
          builder: (context) => Padding(
              padding: const EdgeInsets.all(24),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Text('Size for ${product.name}',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 16),
                Flexible(
                    child: SingleChildScrollView(
                        child: Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final s in product.sizes)
                    ChoiceChip(
                        label: Text(s.name),
                        selected: s.name == item.size,
                        onSelected: s.available && product.inStock != false
                            ? (_) => Navigator.pop(context, s.name)
                            : null)
                ]))),
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cancel')),
              ])));
      if (size == null || size == item.size) return;
      await widget.store.changeSize(item, size);
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Size change could not be confirmed. Review your cart before retrying.');
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
      await widget.store.refreshCart();
      if (mounted) {
        setState(() {
          error = e.message;
          unavailable =
              e.unavailable.map((i) => '${i.productId}:${i.size}').toSet();
        });
      }
    } catch (_) {
      await widget.store.refreshCart();
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
                              trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Text(dollars(p.amountUsd)),
                                    if (!widget.store.demo &&
                                        (p.status == 'nessie_failed' ||
                                            p.status == 'pending_nessie'))
                                      TextButton(
                                          onPressed: busy
                                              ? null
                                              : () => retry(p.retailer),
                                          child: Text(busy
                                              ? 'Retrying…'
                                              : 'Retry payment')),
                                  ]),
                              subtitle: Text(p.status == 'paid'
                                  ? 'Paid in Nessie sandbox'
                                  : p.status == 'demo'
                                      ? 'Demo only'
                                      : p.status == 'pending_nessie'
                                          ? 'Payment pending — not paid'
                                          : 'Payment failed — not charged. You can retry this store only.')),
                        const SizedBox(height: 12),
                        Builder(builder: (context) {
                          final paid = receipt!.purchases
                              .where((p) =>
                                  p.status == 'paid' || p.status == 'demo')
                              .fold<double>(0, (s, p) => s + p.amountUsd);
                          final allPaid = paid >= receipt!.totalUsd - 0.005;
                          return Text(
                              allPaid
                                  ? 'Total ${dollars(receipt!.totalUsd)}'
                                  : 'Paid ${dollars(paid)} of ${dollars(receipt!.totalUsd)}',
                              style: Theme.of(context).textTheme.titleLarge);
                        }),
                        if (error != null)
                          Padding(
                              padding: const EdgeInsets.only(top: 12),
                              child: Text(error!,
                                  style: TextStyle(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .error))),
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
                        if (widget.store.accountWarning != null)
                          ListTile(
                              title: Text(widget.store.accountWarning!),
                              trailing: TextButton(
                                  onPressed: widget.store.load,
                                  child: const Text('Retry'))),
                        if (cart.unavailable.isNotEmpty) ...[
                          const Text('Unavailable pieces',
                              style: TextStyle(fontWeight: FontWeight.w700)),
                          for (final item in cart.unavailable)
                            ListTile(
                                title: Text(item.name),
                                subtitle: Text(
                                    'Size ${item.size} · Qty ${item.qty} · ${item.reason}'),
                                trailing: IconButton(
                                    tooltip: 'Remove unavailable ${item.name}',
                                    icon: const Icon(Icons.close),
                                    onPressed: busy
                                        ? null
                                        : () => remove(CartItem(
                                            productId: item.productId,
                                            size: item.size,
                                            qty: item.qty,
                                            product: item.product)))),
                          const Text(
                              'Remove unavailable pieces before checking out.'),
                        ],
                        for (final group in cart.groups) ...[
                          const SizedBox(height: 24),
                          Text(retailerName(group.retailer),
                              style: Theme.of(context).textTheme.titleLarge),
                          for (final item in group.items)
                            ListTile(
                                contentPadding: EdgeInsets.zero,
                                leading: item.product == null
                                    ? null
                                    : SizedBox(
                                        width: 44,
                                        height: 56,
                                        child: Image.network(
                                            widget.store.imageUrl(
                                                item.product!.imageUrl),
                                            fit: BoxFit.cover,
                                            errorBuilder: (_, e, s) =>
                                                const Icon(
                                                    Icons.checkroom_outlined))),
                                title:
                                    Text(item.product?.name ?? item.productId),
                                subtitle: Text(
                                    'Size ${item.size} · Qty ${item.qty}${unavailable.contains('${item.productId}:${item.size}') ? ' · unavailable' : ''}'),
                                trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                          tooltip:
                                              'Edit size for ${item.product?.name ?? 'item'}',
                                          onPressed: busy
                                              ? null
                                              : () => editSize(item),
                                          icon:
                                              const Icon(Icons.edit_outlined)),
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
                            onPressed: busy ||
                                    cart.unavailable.isNotEmpty ||
                                    widget.store.accountWarning != null
                                ? null
                                : checkout,
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
  final retrying = <String>{};
  String? error;
  Future<void> retry(Order order, Purchase purchase) async {
    final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Retry sandbox payment?'),
                content: Text(
                    'Retry ${retailerName(purchase.retailer)} for ${dollars(purchase.amountUsd)}. Already-paid stores will not be charged again.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Retry'))
                ]));
    if (yes != true || !mounted) return;
    final key = '${order.id}:${purchase.retailer}';
    setState(() => retrying.add(key));
    try {
      await widget.api.retryOrder(order.id, retailer: purchase.retailer);
      if (mounted) setState(() => orders = widget.api.orders());
    } catch (_) {
      if (mounted) {
        setState(() => error =
            'Could not confirm payment. Refresh orders before retrying.');
      }
    } finally {
      if (mounted) setState(() => retrying.remove(key));
    }
  }

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
              if (error != null) Text(error!),
              TextButton(
                  onPressed: () => setState(() => orders = widget.api.orders()),
                  child: const Text('Refresh orders')),
              for (final order in snapshot.data!)
                ExpansionTile(
                    title: Text('Order ${order.id}'),
                    subtitle: Text(dollars(order.totalUsd)),
                    children: [
                      for (final p in order.purchases)
                        ListTile(
                            title: Text(retailerName(p.retailer)),
                            subtitle: Text(p.status),
                            trailing:
                                Row(mainAxisSize: MainAxisSize.min, children: [
                              Text(dollars(p.amountUsd)),
                              if (['nessie_failed', 'pending_nessie']
                                  .contains(p.status))
                                TextButton(
                                    onPressed: retrying.contains(
                                            '${order.id}:${p.retailer}')
                                        ? null
                                        : () => retry(order, p),
                                    child: const Text('Retry payment'))
                            ]))
                    ])
            ]);
          }));
}

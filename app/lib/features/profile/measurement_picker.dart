import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

/// Displays US units; the callback always returns cm/kg (or US shoe size).
class MeasurementPicker extends StatelessWidget {
  const MeasurementPicker(
      {super.key,
      required this.kind,
      required this.value,
      required this.onChanged,
      this.enabled = true});
  final String kind;
  final double? value;
  final ValueChanged<double?> onChanged;
  final bool enabled;
  bool get height => kind.startsWith('Height');
  bool get weight => kind.startsWith('Weight');
  bool get shoe => kind.startsWith('Shoe');
  double get factor => weight
      ? .45359237
      : shoe
          ? 1
          : 2.54;
  String get label => height
      ? 'Height (ft/in)'
      : weight
          ? 'Weight (lb)'
          : kind.replaceAll('(cm)', '(in)');
  String display(double v) => height
      ? '${v.round() ~/ 12} ft ${v.round() % 12} in'
      : '${v.toStringAsFixed(v == v.roundToDouble() ? 0 : 1)} ${weight ? 'lb' : shoe ? 'US' : 'in'}';
  Future<void> choose(BuildContext context) async {
    final values = height
        ? [for (var i = 48; i <= 90; i++) i.toDouble()]
        : weight
            ? [for (var i = 70; i <= 550; i++) i.toDouble()]
            : shoe
                ? [for (var i = 6; i <= 36; i++) i / 2]
                : [for (var i = 24; i <= 160; i++) i / 2];
    var selected = value == null
        ? values.length ~/ 2
        : values.indexWhere((v) => v >= value! / factor);
    if (selected < 0) selected = values.length - 1;
    final result = await showModalBottomSheet<double>(
        context: context,
        useSafeArea: true,
        builder: (context) => SizedBox(
            height: 330,
            child: Column(children: [
              Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(children: [
                    TextButton(
                        onPressed: () => Navigator.pop(context, -1.0),
                        child: const Text('Clear')),
                    Expanded(child: Text(label, textAlign: TextAlign.center)),
                    TextButton(
                        onPressed: () =>
                            Navigator.pop(context, values[selected] * factor),
                        child: const Text('Done'))
                  ])),
              Expanded(
                  child: _MeasurementWheel(
                      values: values,
                      initial: selected,
                      display: display,
                      onChanged: (i) => selected = i)),
            ])));
    if (result != null) onChanged(result < 0 ? null : result);
  }

  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.only(top: 14),
      child: OutlinedButton(
          key: ValueKey('measure-$kind'),
          onPressed: enabled ? () => choose(context) : null,
          child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Row(children: [
                Expanded(child: Text(label)),
                Text(value == null ? 'Optional' : display(value! / factor)),
                const SizedBox(width: 8),
                const Icon(Icons.unfold_more)
              ]))));
}

class _MeasurementWheel extends StatefulWidget {
  const _MeasurementWheel(
      {required this.values,
      required this.initial,
      required this.display,
      required this.onChanged});
  final List<double> values;
  final int initial;
  final String Function(double) display;
  final ValueChanged<int> onChanged;
  @override
  State<_MeasurementWheel> createState() => _MeasurementWheelState();
}

class _MeasurementWheelState extends State<_MeasurementWheel> {
  late final controller =
      FixedExtentScrollController(initialItem: widget.initial);
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => CupertinoPicker(
          scrollController: controller,
          itemExtent: 40,
          onSelectedItemChanged: widget.onChanged,
          children: [
            for (final v in widget.values)
              Center(child: Text(widget.display(v)))
          ]);
}
